import os
import fnmatch
import shutil
from collections import defaultdict

from conans.util.files import mkdir


def report_copied_files(copied, output):
    ext_files = defaultdict(list)
    for f in copied:
        _, ext = os.path.splitext(f)
        ext_files[ext].append(os.path.basename(f))

    if not ext_files:
        return False

    for ext, files in ext_files.items():
        files_str = (", ".join(files)) if len(files) < 5 else ""
        file_or_files = "file" if len(files) == 1 else "files"
        if not ext:
            output.info("Copied %d %s: %s" % (len(files), file_or_files, files_str))
        else:
            output.info("Copied %d '%s' %s: %s" % (len(files), ext, file_or_files, files_str))
    return True


class FileCopier(object):
    """ main responsible of copying files from place to place:
    package: build folder -> package folder
    imports: package folder -> user folder
    export: user folder -> store "export" folder
    """
    def __init__(self, root_source_folder, root_destination_folder, excluded=None):
        """
        Takes the base folders to copy resources src -> dst. These folders names
        will not be used in the relative names while copying
        param root_source_folder: The base folder to copy things from, typically the
                                  store build folder
        param root_destination_folder: The base folder to copy things to, typicall the
                                       store package folder
        """
        self._base_src = root_source_folder
        self._base_dst = root_destination_folder
        self._copied = []
        self._excluded = [root_destination_folder]
        if excluded:
            self._excluded.append(excluded)

    def report(self, output):
        return report_copied_files(self._copied, output)

    def __call__(self, pattern, dst="", src="", keep_path=True, links=False, symlinks=None,
                 excludes=None, ignore_case=False):
        """
        param pattern: an fnmatch file pattern of the files that should be copied. Eg. *.dll
        param dst: the destination local folder, wrt to current conanfile dir, to which
                   the files will be copied. Eg: "bin"
        param src: the source folder in which those files will be searched. This folder
                   will be stripped from the dst name. Eg.: lib/Debug/x86
        param keep_path: False if you want the relative paths to be maintained from
                         src to dst folders, or just drop. False is useful if you want
                         to collect e.g. many *.libs among many dirs into a single
                         lib dir
        return: list of copied files
        """
        if symlinks is not None:
            links = symlinks
        # Check for ../ patterns and allow them
        if pattern.startswith(".."):
            rel_dir = os.path.abspath(os.path.join(self._base_src, pattern))
            base_src = os.path.dirname(rel_dir)
            pattern = os.path.basename(rel_dir)
        else:
            base_src = self._base_src

        src = os.path.join(base_src, src)
        dst = os.path.join(self._base_dst, dst)

        files_to_copy, link_folders, link_files = self._filter_files(src, pattern, links, excludes,
                                                                     ignore_case)

        copied_files = self._copy_files(files_to_copy, src, dst, keep_path, links)
        self._link_elements(src, dst, link_folders + link_files)
        self._copied.extend(files_to_copy)
        return copied_files

    def _filter_files(self, src, pattern, links, excludes, ignore_case):
        """ return a list of the files matching the patterns
        The list will be relative path names wrt to the root src folder
        """
        filepaths = []
        linked_folders = []
        linked_files = []
        for root, subfolders, files in os.walk(src, followlinks=True):
            symlink = False
            if root in self._excluded:
                subfolders[:] = []
                continue
            basename = os.path.basename(root)
            # Skip git or svn subfolders
            if basename in [".git", ".svn"]:
                subfolders[:] = []
                continue
            # DO NOT export test_package/build folder
            if basename == "test_package":
                try:
                    subfolders.remove("build")
                except:
                    pass
            # Mark folder is a symlink
            if os.path.islink(root):
                symlink = os.path.relpath(root, src)

            relative_path = os.path.relpath(root, src)
            for f in files:
                f = os.path.normpath(os.path.join(relative_path, f)).replace("\\", "/")
                if os.path.islink(os.path.join(root, f)):
                    filepaths.append((f, f))
                else:
                    if not symlink:
                        # Check upstream symlinked folders
                        folder_path = src.replace("\\", "/")[:-1]
                        print("file split:", f, f.split("/")[:-1])
                        for folder in f.split("/")[:-1]:
                            folder_path = folder_path + "/" + folder
                            print("folder_path:", folder_path)
                            if os.path.islink(folder_path):
                                symlink = os.path.relpath(folder_path, src)
                                break
                    filepaths.append((f, symlink))

        if ignore_case:
            pattern = pattern.lower()
            filepaths = {(file.lower(), symlink): (file, symlink) for file, symlink in filepaths}
            uncased_filepaths = filepaths

        # Filter fnmatch
        filtered_filepaths = []
        for item in filepaths:
            result = fnmatch.filter([item[0]], pattern)
            if result:
                filtered_filepaths.append((result[0], item[1]))

        if not links:
            withtout_links = []
            for item in filtered_filepaths:
                if not item[1]:
                    withtout_links.append(item)
            filtered_filepaths = withtout_links

        if excludes:
            if not isinstance(excludes, (tuple, list)):
                excludes = (excludes, )
            if ignore_case:
                excludes = [e.lower() for e in excludes]
            for exclude in excludes:
                filtered_filepaths = [f for f in filtered_filepaths if not fnmatch.fnmatch(f[0], exclude)]

        if ignore_case:
            filtered_filepaths = [uncased_filepaths[(file, symlink)] for file, symlink in filtered_filepaths]

        print("FILTERED FILEPATHS:", filtered_filepaths)

        files_to_copy = []
        for item in filtered_filepaths:
            if item[1]:
                if os.path.isdir(os.path.join(src, item[1])):
                    if item[1] not in linked_folders:
                        linked_folders.append(item[1])
                else:
                    if item[1] not in linked_files:
                        linked_files.append(item[1])
            else:
                files_to_copy.append(item[0])

        print("FILES TO COPY:", files_to_copy)
        print("LINKED FOLDERS:", linked_folders)
        print("LINKED FILES:", linked_files)
        return files_to_copy, linked_folders, linked_files

    @staticmethod
    def _link_elements(src, dst, linked_elements):
        # order elements from less dependant to more
        linked_elements_ordered = []
        for link_element in linked_elements:
            if os.readlink(os.path.join(src, link_element)) in linked_elements:
                linked_elements_ordered.append(link_element)
            else:
                linked_elements_ordered.insert(0, link_element)
        for link_element in linked_elements_ordered:
            src_link = os.path.join(src, link_element)  # link element in src
            linked_to_element = os.readlink(src_link)  # 'linked to' element in src
            dst_link = os.path.join(dst, link_element)  # link element in dst
            print("src_link:", src_link)
            print("linked_to_element:", linked_to_element)
            print("dst_link:", dst_link)
            try:
                # Remove the previous symlink
                os.remove(dst_link)
            except OSError:
                pass
            # link is a string relative to linked_element
            # e.g.: os.symlink("test/bar", "./foo/test_link") will create a link to foo/test/bar in ./foo/test_link
            os.symlink(linked_to_element, dst_link)
        # Remove empty links
        for link_element in linked_elements_ordered:
            dst_link = os.path.join(dst, link_element)  # link element in dst
            abs_path = os.path.join(dst, os.readlink(dst_link))
            print("REMOVE dst_link:", dst_link, "REMOVE abs_path:", abs_path)
            if not os.path.exists(abs_path):
                print("REMOVING EMPTY LINK", link_element, abs_path, dst_link)
                os.remove(dst_link)

    @staticmethod
    def _copy_files(files, src, dst, keep_path, symlinks):
        """ executes a multiple file copy from [(src_file, dst_file), (..)]
        managing symlinks if necessary
        """
        copied_files = []
        for filename in files:
            abs_src_name = os.path.join(src, filename)
            filename = filename if keep_path else os.path.basename(filename)
            abs_dst_name = os.path.normpath(os.path.join(dst, filename))
            try:
                os.makedirs(os.path.dirname(abs_dst_name))
            except:
                pass
            if symlinks and os.path.islink(abs_src_name):
                linkto = os.readlink(abs_src_name)  # @UndefinedVariable
                try:
                    os.remove(abs_dst_name)
                except OSError:
                    pass
                os.symlink(linkto, abs_dst_name)  # @UndefinedVariable
            else:
                shutil.copy2(abs_src_name, abs_dst_name)
            copied_files.append(abs_dst_name)
        return copied_files
