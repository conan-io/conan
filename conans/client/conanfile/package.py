import os
import shutil

from conans.client.file_copier import FileCopier
from conans.client.output import ScopedOutput
from conans.client.packager import report_files_from_manifest
from conans.errors import ConanException, conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager
from conans.model.manifest import FileTreeManifest
from conans.paths import CONANINFO
from conans.tools import chdir
from conans.util.conan_v2_mode import conan_v2_property
from conans.util.files import save, mkdir
from conans.util.log import logger


def run_package_method(conanfile, package_id, hook_manager, conanfile_path, ref, copy_info=False):
    """ calls the recipe "package()" method
    - Assigns folders to conanfile.package_folder, source_folder, install_folder, build_folder
    - Calls pre-post package hook
    - Prepares FileCopier helper for self.copy
    """

    if conanfile.package_folder == conanfile.build_folder:
        raise ConanException("Cannot 'conan package' to the build folder. "
                             "--build-folder and package folder can't be the same")

    mkdir(conanfile.package_folder)
    output = conanfile.output
    # Make the copy of all the patterns
    output.info("Generating the package")
    output.info("Package folder %s" % conanfile.package_folder)

    with get_env_context_manager(conanfile):
        return _call_package(conanfile, package_id, hook_manager, conanfile_path, ref, copy_info)


def _call_package(conanfile, package_id, hook_manager, conanfile_path, ref, copy_info):
    output = conanfile.output

    hook_manager.execute("pre_package", conanfile=conanfile, conanfile_path=conanfile_path,
                         reference=ref, package_id=package_id)

    output.highlight("Calling package()")
    folders = [conanfile.source_folder, conanfile.build_folder] \
        if conanfile.source_folder != conanfile.build_folder else [conanfile.build_folder]
    conanfile.copy = FileCopier(folders, conanfile.package_folder)
    with conanfile_exception_formatter(str(conanfile), "package"):
        with chdir(conanfile.build_folder):
            with conan_v2_property(conanfile, 'info',
                                   "'self.info' access in package() method is deprecated"):
                conanfile.package()

    hook_manager.execute("post_package", conanfile=conanfile, conanfile_path=conanfile_path,
                         reference=ref, package_id=package_id)

    manifest = _create_aux_files(conanfile, copy_info)
    package_output = ScopedOutput("%s package()" % output.scope, output)
    report_files_from_manifest(package_output, manifest)
    package_id = package_id or os.path.basename(conanfile.package_folder)

    output.success("Package '%s' created" % package_id)

    prev = manifest.summary_hash
    output.info("Created package revision %s" % prev)
    return prev


def _create_aux_files(conanfile, copy_info):
    """ auxiliary method that creates CONANINFO and manifest in
    the package_folder
    """
    logger.debug("PACKAGE: Creating config files to %s" % conanfile.package_folder)
    if copy_info:
        try:
            shutil.copy(os.path.join(conanfile.install_folder, CONANINFO),
                        conanfile.package_folder)
        except IOError:
            raise ConanException("%s does not exist inside of your %s folder. "
                                 "Try to re-build it again to solve it."
                                 % (CONANINFO, conanfile.install_folder))
    else:
        save(os.path.join(conanfile.package_folder, CONANINFO), conanfile.info.dumps())

    # Create the digest for the package
    manifest = FileTreeManifest.create(conanfile.package_folder)
    manifest.save(conanfile.package_folder)
    return manifest
