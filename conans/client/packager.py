import os
import shutil

from conans.client import tools
from conans.util.files import mkdir, save, rmdir
from conans.util.log import logger
from conans.paths import CONANINFO, CONAN_MANIFEST
from conans.errors import ConanException, ConanExceptionInUserConanfileMethod, conanfile_exception_formatter
from conans.model.manifest import FileTreeManifest
from conans.client.output import ScopedOutput
from conans.client.file_copier import FileCopier


def create_package(conanfile, source_folder, build_folder, package_folder, install_folder,
                   output, local=False, copy_info=False):
    """ copies built artifacts, libs, headers, data, etc from build_folder to
    package folder
    """
    mkdir(package_folder)

    # Make the copy of all the patterns
    output.info("Generating the package")
    output.info("Package folder %s" % (package_folder))

    try:
        package_output = ScopedOutput("%s package()" % output.scope, output)
        output.highlight("Calling package()")
        conanfile.package_folder = package_folder
        conanfile.source_folder = source_folder
        conanfile.install_folder = install_folder
        conanfile.build_folder = build_folder

        def recipe_has(conanfile, attribute):
            return attribute in conanfile.__class__.__dict__

        if source_folder != build_folder:
            conanfile.copy = FileCopier(source_folder, package_folder, build_folder)
            with conanfile_exception_formatter(str(conanfile), "package"):
                with tools.chdir(source_folder):
                    conanfile.package()
            warn = recipe_has(conanfile, "package")
            conanfile.copy.report(package_output, warn=warn)

        conanfile.copy = FileCopier(build_folder, package_folder)
        with tools.chdir(build_folder):
            with conanfile_exception_formatter(str(conanfile), "package"):
                conanfile.package()
        warn = recipe_has(conanfile, "build") and recipe_has(conanfile, "package")
        conanfile.copy.report(package_output, warn=warn)
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
    output.success("Package '%s' created" % os.path.basename(package_folder))


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
    save(os.path.join(package_folder, CONAN_MANIFEST), str(digest))
