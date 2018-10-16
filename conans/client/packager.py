import os
import shutil

from conans.client import tools
from conans.util.files import mkdir, save, rmdir
from conans.util.log import logger
from conans.paths import CONANINFO
from conans.errors import ConanException, ConanExceptionInUserConanfileMethod, conanfile_exception_formatter
from conans.model.manifest import FileTreeManifest
from conans.client.output import ScopedOutput
from conans.client.file_copier import FileCopier


def export_pkg(conanfile, pkg_id, src_package_folder, package_folder, output, plugin_manager,
               conanfile_path, reference):
    mkdir(package_folder)
    conanfile.package_folder = src_package_folder
    output.info("Exporting to cache existing package from user folder")
    output.info("Package folder %s" % package_folder)
    print("export_pkg", type(reference))
    plugin_manager.execute("pre_package", conanfile=conanfile, conanfile_path=conanfile_path,
                           reference=reference, package_id=pkg_id)

    copier = FileCopier(src_package_folder, package_folder)
    copier("*", symlinks=True)

    copy_done = copier.report(output)
    if not copy_done:
        output.warn("No files copied from package folder!")

    save(os.path.join(package_folder, CONANINFO), conanfile.info.dumps())
    digest = FileTreeManifest.create(package_folder)
    digest.save(package_folder)
    output.success("Package '%s' created" % pkg_id)
    conanfile.package_folder = package_folder
    plugin_manager.execute("post_package", conanfile=conanfile, conanfile_path=conanfile_path,
                           reference=reference, package_id=pkg_id)


def create_package(conanfile, pkg_id, source_folder, build_folder, package_folder, install_folder,
                   output, plugin_manager, conanfile_path, reference, local=False, copy_info=False):
    """ copies built artifacts, libs, headers, data, etc. from build_folder to
    package folder
    """
    mkdir(package_folder)

    # Make the copy of all the patterns
    output.info("Generating the package")
    output.info("Package folder %s" % package_folder)

    try:
        conanfile.package_folder = package_folder
        conanfile.source_folder = source_folder
        conanfile.install_folder = install_folder
        conanfile.build_folder = build_folder

        plugin_manager.execute("pre_package", conanfile=conanfile, conanfile_path=conanfile_path,
                               reference=reference, package_id=pkg_id)

        package_output = ScopedOutput("%s package()" % output.scope, output)
        output.highlight("Calling package()")

        def recipe_has(attribute):
            return attribute in conanfile.__class__.__dict__

        if source_folder != build_folder:
            conanfile.copy = FileCopier(source_folder, package_folder, build_folder)
            with conanfile_exception_formatter(str(conanfile), "package"):
                with tools.chdir(source_folder):
                    conanfile.package()
            copy_done = conanfile.copy.report(package_output)
            if not copy_done and recipe_has("package"):
                output.warn("No files copied from source folder!")

        conanfile.copy = FileCopier(build_folder, package_folder)
        with tools.chdir(build_folder):
            with conanfile_exception_formatter(str(conanfile), "package"):
                conanfile.package()
        copy_done = conanfile.copy.report(package_output)
        if not copy_done and recipe_has("build") and recipe_has("package"):
            output.warn("No files copied from build folder!")
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
    pkg_id = pkg_id or os.path.basename(package_folder)
    output.success("Package '%s' created" % pkg_id)
    plugin_manager.execute("post_package", conanfile=conanfile, conanfile_path=conanfile_path,
                           reference=reference, package_id=pkg_id)


def _create_aux_files(install_folder, package_folder, conanfile, copy_info):
    """ auxiliary method that creates CONANINFO and manifest in
    the package_folder
    """
    logger.debug("Creating config files to %s" % package_folder)
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
