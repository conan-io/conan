import os
import fnmatch
from conans.model.ref import PackageReference
from conans.client.file_copier import FileCopier


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
    def __init__(self, deps_graph, paths, dst_folder):
        self._graph = deps_graph
        self._paths = paths
        self._dst_folder = dst_folder
        self._copies = []

    def __call__(self, pattern, dst="", src="", root_package="*"):
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

    def _get_folders(self):
        """ given the current deps graph, compute a dict {name: store-path} of
        each dependency
        """
        package_folders = {}
        for node in self._graph.nodes:
            conan_ref, conan_file = node
            if not conan_ref:
                continue
            package_id = conan_file.info.package_id()
            package_reference = PackageReference(conan_ref, package_id)
            short_paths = "check" if conan_file.short_paths else False
            package_folders[conan_file.name] = self._paths.package(package_reference, short_paths)
        return package_folders

    def _get_paths(self, conan_name_pattern):
        """ returns all the base paths of the dependencies matching the
        root_package pattern
        """
        result_paths = []
        folders = self._get_folders()
        for name, path in folders.items():
            if fnmatch.fnmatch(name, conan_name_pattern):
                result_paths.append(path)
        return result_paths

    def execute(self):
        """ Execute the stored requested copies, using a FileCopier as helper
        return: set of copied files
        """
        root_src_folder = self._paths.store
        file_copier = FileCopier(root_src_folder, self._dst_folder)
        copied_files = set()
        for pattern, dst_folder, src_folder, conan_name_pattern in self._copies:
            if os.path.isabs(dst_folder):
                real_dst_folder = dst_folder
            else:
                real_dst_folder = os.path.normpath(os.path.join(self._dst_folder, dst_folder))
            matching_paths = self._get_paths(conan_name_pattern)
            for matching_path in matching_paths:
                real_src_folder = os.path.join(matching_path, src_folder)
                files = file_copier(pattern, real_dst_folder, real_src_folder)
                copied_files.update(files)
        return copied_files
