import calendar
import fnmatch
import os
import time

from conans.client.file_copier import FileCopier, report_copied_files
from conans.client.output import ScopedOutput
from conans.errors import ConanException
from conans.model.manifest import FileTreeManifest
from conans.tools import environment_append
from conans.util.files import save, md5sum, load

IMPORTS_MANIFESTS = "conan_imports_manifest.txt"


def undo_imports(current_path, output):
    manifest_path = os.path.join(current_path, IMPORTS_MANIFESTS)
    try:
        manifest_content = load(manifest_path)
    except:
        raise ConanException("Cannot load file %s" % manifest_path)

    try:
        manifest = FileTreeManifest.loads(manifest_content)
    except:
        raise ConanException("Wrong manifest file format %s" % manifest_path)

    not_removed = 0
    files = manifest.files()
    for filepath in files:
        if not os.path.exists(filepath):
            output.warn("File doesn't exist: %s" % filepath)
            continue
        try:
            os.remove(filepath)
        except:
            output.error("Cannot remove file (open or busy): %s" % filepath)
            not_removed += 1

    if not_removed:
        raise ConanException("Cannot remove %s or more imported files" % not_removed)

    output.success("Removed %s imported files" % (len(files)))
    try:
        os.remove(manifest_path)
        output.success("Removed imports manifest file: %s" % manifest_path)
    except:
        raise ConanException("Cannot remove manifest file (open or busy): %s" % manifest_path)


def run_imports(conanfile, dest_folder, output):
    file_importer = FileImporter(conanfile, dest_folder)
    conanfile.copy = file_importer
    with environment_append(conanfile.env):
        conanfile.imports()
    copied_files = file_importer.execute()
    import_output = ScopedOutput("%s imports()" % output.scope, output)
    report_copied_files(copied_files, import_output)
    if copied_files:
        date = calendar.timegm(time.gmtime())
        file_dict = {}
        for f in copied_files:
            abs_path = os.path.join(dest_folder, f)
            file_dict[f] = md5sum(abs_path)
        manifest = FileTreeManifest(date, file_dict)
        save(os.path.join(dest_folder, IMPORTS_MANIFESTS), str(manifest))
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
