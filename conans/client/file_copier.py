import os
import fnmatch
import shutil
from collections import defaultdict


def report_copied_files(copied, output, warn=False):
    ext_files = defaultdict(list)
    for f in copied:
        _, ext = os.path.splitext(f)
        ext_files[ext].append(os.path.basename(f))

    for ext, files in ext_files.items():
        files_str = (": " + ", ".join(files)) if len(files)<5 else ""
        output.info("Copied %d '%s' files%s" % (len(files), ext, files_str))

    if warn and not ext_files:
        output.warn("No files copied!")

class FileCopier(object):
    """ main responsible of copying files from place to place:
    package: build folder -> package folder
    imports: package folder -> user folder
    export: user folder -> store "export" folder
    """
    def __init__(self, root_source_folder, root_destination_folder):
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
 
    def report(self, output, warn=False):
        report_copied_files(self._copied, output, warn)

    def __call__(self, pattern, dst="", src="", keep_path=True):
        """ FileCopier is lazy, it just store requested copies, and execute them later
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
        # Check for ../ patterns and allow them
        reldir = os.path.abspath(os.path.join(self._base_src, pattern))
        if self._base_src.startswith(os.path.dirname(reldir)):  # ../ relative dir
            self._base_src = os.path.dirname(reldir)
            pattern = os.path.basename(reldir)

        copied_files = []
        src = os.path.join(self._base_src, src)
        dst = os.path.join(self._base_dst, dst)
        for root, subfolders, files in os.walk(src,followlinks=True):
            # do the copy
            relative_path = os.path.relpath(root, src)
            # Skip git or svn subfolders
            if os.path.basename(root) in [".git", ".svn"]:
                subfolders[:] = []
                continue
            for f in files:
                relative_name = os.path.normpath(os.path.join(relative_path, f))
                if fnmatch.fnmatch(relative_name, pattern):
                    abs_src_name = os.path.join(root, f)
                    filename = relative_name if keep_path else f
                    abs_dst_name = os.path.normpath(os.path.join(dst, filename))
                    try:
                        os.makedirs(os.path.dirname(abs_dst_name))
                    except:
                        pass
                    shutil.copy2(abs_src_name, abs_dst_name)
                    copied_files.append(abs_dst_name)
                    self._copied.append(relative_name)
        return copied_files
