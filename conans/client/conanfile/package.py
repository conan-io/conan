import os
import shutil

from conans.client.file_copier import FileCopier
from conans.client.output import ScopedOutput
from conans.client.packager import report_files_from_manifest
from conans.errors import ConanException, ConanExceptionInUserConanfileMethod, \
    conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager
from conans.model.manifest import FileTreeManifest
from conans.paths import CONANINFO
from conans.tools import chdir
from conans.util.conan_v2_mode import conan_v2_property
from conans.util.files import save, mkdir, rmdir
from conans.util.log import logger


def run_package_method(conanfile, package_id, source_folder, build_folder, package_folder,
                       install_folder, hook_manager, conanfile_path, ref, local=False,
                       copy_info=False):
    """ calls the recipe "package()" method
    - Assigns folders to conanfile.package_folder, source_folder, install_folder, build_folder
    - Calls pre-post package hook
    - Prepares FileCopier helper for self.copy
    """
    mkdir(package_folder)
    output = conanfile.output
    # Make the copy of all the patterns
    output.info("Generating the package")
    output.info("Package folder %s" % package_folder)

    conanfile.package_folder = package_folder
    conanfile.source_folder = source_folder
    conanfile.install_folder = install_folder
    conanfile.build_folder = build_folder

    with get_env_context_manager(conanfile):
        return _call_package(conanfile, package_id, source_folder, build_folder, package_folder,
                             install_folder, hook_manager, conanfile_path, ref, local, copy_info)


def _call_package(conanfile, package_id, source_folder, build_folder, package_folder,
                  install_folder, hook_manager, conanfile_path, ref, local, copy_info):
    output = conanfile.output
    try:
        hook_manager.execute("pre_package", conanfile=conanfile, conanfile_path=conanfile_path,
                             reference=ref, package_id=package_id)

        output.highlight("Calling package()")
        folders = [source_folder, build_folder] if source_folder != build_folder else [build_folder]
        conanfile.copy = FileCopier(folders, package_folder)
        with conanfile_exception_formatter(str(conanfile), "package"):
            with chdir(build_folder):
                with conan_v2_property(conanfile, 'info',
                                       "'self.info' access in package() method is deprecated"):
                    conanfile.package()
    except Exception as e:
        if not local:
            os.chdir(build_folder)
            try:
                rmdir(package_folder)
            except Exception as e_rm:
                output.error("Unable to remove package folder %s\n%s" % (package_folder, str(e_rm)))
                output.warn("**** Please delete it manually ****")

        if isinstance(e, ConanExceptionInUserConanfileMethod):
            raise
        raise ConanException(e)

    hook_manager.execute("post_package", conanfile=conanfile, conanfile_path=conanfile_path,
                         reference=ref, package_id=package_id)

    manifest = _create_aux_files(install_folder, package_folder, conanfile, copy_info)
    package_output = ScopedOutput("%s package()" % output.scope, output)
    report_files_from_manifest(package_output, manifest)
    package_id = package_id or os.path.basename(package_folder)

    output.success("Package '%s' created" % package_id)

    prev = manifest.summary_hash
    output.info("Created package revision %s" % prev)
    return prev


def _create_aux_files(install_folder, package_folder, conanfile, copy_info):
    """ auxiliary method that creates CONANINFO and manifest in
    the package_folder
    """
    logger.debug("PACKAGE: Creating config files to %s" % package_folder)
    if copy_info:
        try:
            shutil.copy(os.path.join(install_folder, CONANINFO), package_folder)
        except IOError:
            raise ConanException("%s does not exist inside of your %s folder. "
                                 "Try to re-build it again to solve it."
                                 % (CONANINFO, install_folder))
    else:
        save(os.path.join(package_folder, CONANINFO), conanfile.info.dumps())

    # Create the digest for the package
    manifest = FileTreeManifest.create(package_folder)
    manifest.save(package_folder)
    return manifest
