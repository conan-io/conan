import calendar
import fnmatch
import os
import time

from conans import tools
from conans.client.file_copier import FileCopier, report_copied_files
from conans.client.output import ScopedOutput
from conans.errors import ConanException
from conans.model.conan_file import get_env_context_manager
from conans.model.manifest import FileTreeManifest
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


def _report_save_manifest(copied_files, output, dest_folder, manifest_name):
    report_copied_files(copied_files, output)
    if copied_files:
        date = calendar.timegm(time.gmtime())
        file_dict = {}
        for f in copied_files:
            abs_path = os.path.join(dest_folder, f)
            file_dict[f] = md5sum(abs_path)
        manifest = FileTreeManifest(date, file_dict)
        save(os.path.join(dest_folder, manifest_name), str(manifest))


def run_imports(conanfile, dest_folder, output):
    if not hasattr(conanfile, "imports"):
        return []
    file_importer = _FileImporter(conanfile, dest_folder)
    conanfile.copy = file_importer
    conanfile.imports_folder = dest_folder
    with get_env_context_manager(conanfile):
        with tools.chdir(dest_folder):
            conanfile.imports()
    copied_files = file_importer.copied_files
    import_output = ScopedOutput("%s imports()" % output.scope, output)
    _report_save_manifest(copied_files, import_output, dest_folder, IMPORTS_MANIFESTS)
    return copied_files


def run_deploy(conanfile, install_folder, output):
    deploy_output = ScopedOutput("%s deploy()" % output.scope, output)
    file_importer = _FileImporter(conanfile, install_folder)
    package_copied = set()

    # This is necessary to capture FileCopier full destination paths
    # Maybe could be improved in FileCopier
    def file_copier(*args, **kwargs):
        file_copy = FileCopier(conanfile.package_folder, install_folder)
        copied = file_copy(*args, **kwargs)
        package_copied.update(copied)

    conanfile.copy_deps = file_importer
    conanfile.copy = file_copier
    conanfile.install_folder = install_folder
    with get_env_context_manager(conanfile):
        with tools.chdir(install_folder):
            conanfile.deploy()

    copied_files = file_importer.copied_files
    copied_files.update(package_copied)
    _report_save_manifest(copied_files, deploy_output, install_folder, "deploy_manifest.txt")


class _FileImporter(object):
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
        self.copied_files = set()

    def __call__(self, pattern, dst="", src="", root_package=None, folder=False,
                 ignore_case=False, excludes=None, keep_path=True):
        """
        param pattern: an fnmatch file pattern of the files that should be copied. Eg. *.dll
        param dst: the destination local folder, wrt to current conanfile dir, to which
                   the files will be copied. Eg: "bin"
        param src: the source folder in which those files will be searched. This folder
                   will be stripped from the dst name. Eg.: lib/Debug/x86
        param root_package: fnmatch pattern of the package name ("OpenCV", "Boost") from
                            which files will be copied. Default: all packages in deps
        """
        if os.path.isabs(dst):
            real_dst_folder = dst
        else:
            real_dst_folder = os.path.normpath(os.path.join(self._dst_folder, dst))

        matching_paths = self._get_folders(root_package)
        for name, matching_path in matching_paths.items():
            final_dst_path = os.path.join(real_dst_folder, name) if folder else real_dst_folder
            file_copier = FileCopier(matching_path, final_dst_path)
            files = file_copier(pattern, src=src, links=True, ignore_case=ignore_case,
                                excludes=excludes, keep_path=keep_path)
            self.copied_files.update(files)

    def _get_folders(self, pattern):
        """ given the current deps graph, compute a dict {name: store-path} of
        each dependency
        """
        if not pattern:
            return {pkg: cpp_info.rootpath for pkg, cpp_info in self._conanfile.deps_cpp_info.dependencies}
        return {pkg: cpp_info.rootpath for pkg, cpp_info in self._conanfile.deps_cpp_info.dependencies
                if fnmatch.fnmatch(pkg, pattern)}
