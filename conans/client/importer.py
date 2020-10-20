import calendar
import fnmatch
import os
import stat
import time

from conans.client import tools
from conans.client.file_copier import FileCopier, report_copied_files
from conans.client.output import ScopedOutput
from conans.errors import ConanException
from conans.model.conan_file import get_env_context_manager
from conans.model.manifest import FileTreeManifest
from conans.util.env_reader import get_env
from conans.util.files import load, md5sum

IMPORTS_MANIFESTS = "conan_imports_manifest.txt"


def undo_imports(current_path, output):
    manifest_path = os.path.join(current_path, IMPORTS_MANIFESTS)
    try:
        manifest_content = load(manifest_path)
    except Exception:
        raise ConanException("Cannot load file %s" % manifest_path)

    try:
        manifest = FileTreeManifest.loads(manifest_content)
    except Exception:
        raise ConanException("Wrong manifest file format %s" % manifest_path)

    not_removed = 0
    files = manifest.files()
    for filepath in files:
        if not os.path.exists(filepath):
            output.warn("File doesn't exist: %s" % filepath)
            continue
        try:
            os.remove(filepath)
        except OSError:
            output.error("Cannot remove file (open or busy): %s" % filepath)
            not_removed += 1

    if not_removed:
        raise ConanException("Cannot remove %s or more imported files" % not_removed)

    output.success("Removed %s imported files" % (len(files)))
    try:
        os.remove(manifest_path)
        output.success("Removed imports manifest file: %s" % manifest_path)
    except Exception:
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
        manifest.save(dest_folder, manifest_name)


def _make_files_writable(file_names):
    if not get_env("CONAN_READ_ONLY_CACHE", False):
        return

    for file_name in file_names:
        os.chmod(file_name, os.stat(file_name).st_mode | stat.S_IWRITE)


def run_imports(conanfile, dest_folder):
    if not hasattr(conanfile, "imports"):
        return []
    file_importer = _FileImporter(conanfile, dest_folder)
    conanfile.copy = file_importer
    conanfile.imports_folder = dest_folder
    with get_env_context_manager(conanfile):
        with tools.chdir(dest_folder):
            conanfile.imports()
    copied_files = file_importer.copied_files
    _make_files_writable(copied_files)
    import_output = ScopedOutput("%s imports()" % conanfile.display_name, conanfile.output)
    _report_save_manifest(copied_files, import_output, dest_folder, IMPORTS_MANIFESTS)
    return copied_files


def remove_imports(conanfile, copied_files, output):
    if not getattr(conanfile, "keep_imports", False):
        for f in copied_files:
            try:
                os.remove(f)
            except OSError:
                output.warn("Unable to remove imported file from build: %s" % f)


def run_deploy(conanfile, install_folder):
    deploy_output = ScopedOutput("%s deploy()" % conanfile.display_name, conanfile.output)
    file_importer = _FileImporter(conanfile, install_folder)
    package_copied = set()

    # This is necessary to capture FileCopier full destination paths
    # Maybe could be improved in FileCopier
    def file_copier(*args, **kwargs):
        file_copy = FileCopier([conanfile.package_folder], install_folder)
        copied = file_copy(*args, **kwargs)
        _make_files_writable(copied)
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
                 ignore_case=True, excludes=None, keep_path=True):
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

        pkgs = (self._conanfile.deps_cpp_info.dependencies if not root_package else
                [(pkg, cpp_info) for pkg, cpp_info in self._conanfile.deps_cpp_info.dependencies
                 if fnmatch.fnmatch(pkg, root_package)])

        symbolic_dir_name = src[1:] if src.startswith("@") else None
        src_dirs = [src]  # hardcoded src="bin" origin
        for pkg_name, cpp_info in pkgs:
            final_dst_path = os.path.join(real_dst_folder, pkg_name) if folder else real_dst_folder
            file_copier = FileCopier([cpp_info.rootpath], final_dst_path)
            if symbolic_dir_name:  # Syntax for package folder symbolic names instead of hardcoded
                try:
                    src_dirs = getattr(cpp_info, symbolic_dir_name)
                    if not isinstance(src_dirs, list):  # it can return a "config" CppInfo item!
                        raise AttributeError
                except AttributeError:
                    raise ConanException("Import from unknown package folder '@%s'"
                                         % symbolic_dir_name)

            for src_dir in src_dirs:
                files = file_copier(pattern, src=src_dir, links=True, ignore_case=ignore_case,
                                    excludes=excludes, keep_path=keep_path)
                self.copied_files.update(files)
