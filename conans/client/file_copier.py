import os
import fnmatch
import shutil
from collections import defaultdict

from conans.util.files import mkdir, walk


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

        files_to_copy, link_folders = self._filter_files(src, pattern, links, excludes,
                                                         ignore_case)
        copied_files = self._copy_files(files_to_copy, src, dst, keep_path, links)
        self._link_folders(src, dst, link_folders)
        self._copied.extend(files_to_copy)
        return copied_files

    def _filter_files(self, src, pattern, links, excludes, ignore_case):

        """ return a list of the files matching the patterns
        The list will be relative path names wrt to the root src folder
        """
        filenames = []
        linked_folders = []

        if excludes:
            if not isinstance(excludes, (tuple, list)):
                excludes = (excludes, )
            if ignore_case:
                excludes = [e.lower() for e in excludes]
        else:
            excludes = []

        for root, subfolders, files in walk(src, followlinks=True):
            if root in self._excluded:
                subfolders[:] = []
                continue

            if links and os.path.islink(root):
                linked_folders.append(os.path.relpath(root, src))
                subfolders[:] = []
                continue
            basename = os.path.basename(root)
            # Skip git or svn subfolders
            if basename in [".git", ".svn"]:
                subfolders[:] = []
                continue
            if basename == "test_package":  # DO NOT export test_package/build folder
                try:
                    subfolders.remove("build")
                except:
                    pass

            relative_path = os.path.relpath(root, src)
            for exclude in excludes:
                if fnmatch.fnmatch(relative_path, exclude):
                    subfolders[:] = []
                    files = []
                    break
            for f in files:
                relative_name = os.path.normpath(os.path.join(relative_path, f))
                filenames.append(relative_name)

        if ignore_case:
            filenames = {f.lower(): f for f in filenames}
            pattern = pattern.lower()

        files_to_copy = fnmatch.filter(filenames, pattern)
        for exclude in excludes:
            files_to_copy = [f for f in files_to_copy if not fnmatch.fnmatch(f, exclude)]

        if ignore_case:
            files_to_copy = [filenames[f] for f in files_to_copy]

        return files_to_copy, linked_folders

    @staticmethod
    def _link_folders(src, dst, linked_folders):
        created_links = []
        for linked_folder in linked_folders:
            src_link = os.path.join(src, linked_folder)
            # Discard symlinks that go out of the src folder
            abs_path = os.path.realpath(src_link)
            relpath = os.path.relpath(abs_path, src)
            if relpath.startswith("."):
                continue
            
            link = os.readlink(src_link)
            # Absoluted path symlinks are a problem, convert it to relative
            if os.path.isabs(link):
                link = os.path.relpath(link, os.path.dirname(src_link))

            dst_link = os.path.join(dst, linked_folder)
            try:
                # Remove the previous symlink
                os.remove(dst_link)
            except OSError:
                pass
            # link is a string relative to linked_folder
            # e.g.: os.symlink("test/bar", "./foo/test_link") will create a link to foo/test/bar in ./foo/test_link
            mkdir(os.path.dirname(dst_link))
            os.symlink(link, dst_link)
            created_links.append(dst_link)
        # Remove empty links
        for dst_link in created_links:
            abs_path = os.path.realpath(dst_link)
            if not os.path.exists(abs_path):
                base_path = os.path.dirname(dst_link)
                os.remove(dst_link)
                while base_path.startswith(dst):
                    try:  # Take advantage that os.rmdir does not delete non-empty dirs
                        os.rmdir(base_path)
                    except OSError:
                        break  # not empty
                    base_path = os.path.dirname(base_path)

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
