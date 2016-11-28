import os
import fnmatch

from conans.client.file_copier import FileCopier, report_copied_files
from conans.client.output import ScopedOutput


def run_imports(conanfile, current_path, output):
    file_importer = FileImporter(conanfile, current_path)
    conanfile.copy = file_importer
    conanfile.imports()
    copied_files = file_importer.execute()
    import_output = ScopedOutput("%s imports()" % output.scope, output)
    report_copied_files(copied_files, import_output)
    return copied_files


class FileImporter(object):
    """ manages the copy of files, resources, libs from the local store to the user
    space. E.g.: shared libs, dlls, they will be in the package folder of your
    configuration in the store. But you dont want to add every package to the
    system PATH. Those shared libs can be copied to the user folder, close to
    the exes where they can be found without modifying the path.
    Useful also for copying other resources as images or data files.
    It can be also used for Golang projects, in which the packages are always
    source based and need to be copied to the user folder to be built
    """
    def __init__(self, conanfile, dst_folder):
        self._conanfile = conanfile
        self._dst_folder = dst_folder
        self._copies = []

    def __call__(self, pattern, dst="", src="", root_package=None):
        """ FileImporter is lazy, it just store requested copies, and execute them later
        param pattern: an fnmatch file pattern of the files that should be copied. Eg. *.dll
        param dst: the destination local folder, wrt to current conanfile dir, to which
                   the files will be copied. Eg: "bin"
        param src: the source folder in which those files will be searched. This folder
                   will be stripped from the dst name. Eg.: lib/Debug/x86
        param root_package: fnmatch pattern of the package name ("OpenCV", "Boost") from
                            which files will be copied. Default: all packages in deps
        """
        self._copies.append((pattern, dst, src, root_package))

    def _get_folders(self, pattern):
        """ given the current deps graph, compute a dict {name: store-path} of
        each dependency
        """
        package_folders = []
        if not pattern:
            for name, deps_info in self._conanfile.deps_cpp_info.dependencies:
                package_folders.append(deps_info.rootpath)
        else:
            for name, deps_info in self._conanfile.deps_cpp_info.dependencies:
                if fnmatch.fnmatch(name, pattern):
                    package_folders.append(deps_info.rootpath)
        return package_folders

    def execute(self):
        """ Execute the stored requested copies, using a FileCopier as helper
        return: set of copied files
        """
        copied_files = set()
        for pattern, dst_folder, src_folder, conan_name_pattern in self._copies:
            if os.path.isabs(dst_folder):
                real_dst_folder = dst_folder
            else:
                real_dst_folder = os.path.normpath(os.path.join(self._dst_folder, dst_folder))

            matching_paths = self._get_folders(conan_name_pattern)
            for matching_path in matching_paths:
                file_copier = FileCopier(matching_path, real_dst_folder)
                files = file_copier(pattern, src=src_folder, links=True)
                copied_files.update(files)
        return copied_files
