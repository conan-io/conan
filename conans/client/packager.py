import os
import shutil

from conans.client.file_copier import FileCopier, report_copied_files
from conans.client.output import ScopedOutput
from conans.client.tools.files import chdir
from conans.errors import (ConanException, ConanExceptionInUserConanfileMethod,
                           conanfile_exception_formatter)
from conans.model.manifest import FileTreeManifest
from conans.paths import CONANINFO
from conans.util.files import mkdir, rmdir, save
from conans.util.log import logger


def export_pkg(conanfile, package_id, src_package_folder, package_folder, hook_manager,
               conanfile_path, ref):
    mkdir(package_folder)
    conanfile.package_folder = src_package_folder
    output = conanfile.output
    output.info("Exporting to cache existing package from user folder")
    output.info("Package folder %s" % package_folder)
    hook_manager.execute("pre_package", conanfile=conanfile, conanfile_path=conanfile_path,
                         reference=ref, package_id=package_id)

    copier = FileCopier([src_package_folder], package_folder)
    copier("*", symlinks=True)

    save(os.path.join(package_folder, CONANINFO), conanfile.info.dumps())
    digest = FileTreeManifest.create(package_folder)
    digest.save(package_folder)

    _report_files_from_manifest(output, package_folder)

    output.success("Package '%s' created" % package_id)
    conanfile.package_folder = package_folder
    hook_manager.execute("post_package", conanfile=conanfile, conanfile_path=conanfile_path,
                         reference=ref, package_id=package_id)


def create_package(conanfile, package_id, source_folder, build_folder, package_folder,
                   install_folder, hook_manager, conanfile_path, ref, local=False,
                   copy_info=False):
    """ copies built artifacts, libs, headers, data, etc. from build_folder to
    package folder
    """
    mkdir(package_folder)
    output = conanfile.output
    # Make the copy of all the patterns
    output.info("Generating the package")
    output.info("Package folder %s" % package_folder)

    try:
        conanfile.package_folder = package_folder
        conanfile.source_folder = source_folder
        conanfile.install_folder = install_folder
        conanfile.build_folder = build_folder

        hook_manager.execute("pre_package", conanfile=conanfile, conanfile_path=conanfile_path,
                             reference=ref, package_id=package_id)

        package_output = ScopedOutput("%s package()" % output.scope, output)
        output.highlight("Calling package()")

        folders = [source_folder, build_folder] if source_folder != build_folder else [build_folder]
        conanfile.copy = FileCopier(folders, package_folder)
        with conanfile_exception_formatter(str(conanfile), "package"):
            with chdir(build_folder):
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

    _create_aux_files(install_folder, package_folder, conanfile, copy_info)
    _report_files_from_manifest(package_output, package_folder)
    package_id = package_id or os.path.basename(package_folder)
    output.success("Package '%s' created" % package_id)
    hook_manager.execute("post_package", conanfile=conanfile, conanfile_path=conanfile_path,
                         reference=ref, package_id=package_id)


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
    digest = FileTreeManifest.create(package_folder)
    digest.save(package_folder)


def _report_files_from_manifest(output, package_folder):
    digest = FileTreeManifest.load(package_folder)
    copied_files = list(digest.files())
    copied_files.remove(CONANINFO)

    if not copied_files:
        output.warn("No files in this package!")
        return

    report_copied_files(copied_files, output, message_suffix="Packaged")
