import os
import fnmatch
import shutil


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
        self._copies = []

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
        """
        self._copies.append((pattern, dst, src, keep_path))

    def execute(self):
        """ execute the stored requested copy
        """
        for pattern, dst_folder, src_folder, keep_path in self._copies:
            root_src_folder = os.path.join(self._base_src, src_folder)
            root_dst_folder = os.path.join(self._base_dst, dst_folder)
            for root, subfolders, files in os.walk(root_src_folder):
                # do the copy
                relative_path = os.path.relpath(root, root_src_folder)
                # Skip git or svn subfolders
                if os.path.basename(root) in [".git", ".svn"]:
                    subfolders[:] = []
                    continue
                for f in files:
                    relative_name = os.path.normpath(os.path.join(relative_path, f))
                    if fnmatch.fnmatch(relative_name, pattern):
                        abs_src_name = os.path.join(root, f)
                        filename = relative_name if keep_path else f
                        abs_dst_name = os.path.normpath(os.path.join(root_dst_folder, filename))
                        try:
                            os.makedirs(os.path.dirname(abs_dst_name))
                        except:
                            pass
                        shutil.copy2(abs_src_name, abs_dst_name)
