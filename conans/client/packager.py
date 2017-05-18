import os
import shutil

from conans.util.files import mkdir, save, rmdir
from conans.util.log import logger
from conans.paths import CONANINFO, CONAN_MANIFEST
from conans.errors import ConanException, ConanExceptionInUserConanfileMethod, conanfile_exception_formatter
from conans.model.build_info import DEFAULT_RES, DEFAULT_BIN, DEFAULT_LIB, DEFAULT_INCLUDE
from conans.model.manifest import FileTreeManifest
from conans.client.output import ScopedOutput
from conans.client.file_copier import FileCopier


def create_package(conanfile, source_folder, build_folder, package_folder, output, local=False):
    """ copies built artifacts, libs, headers, data, etc from build_folder to
    package folder
    """
    mkdir(package_folder)

    # Make the copy of all the patterns
    output.info("Generating the package")
    output.info("Package folder %s" % (package_folder))

    def wrap(dst_folder):
        def new_method(pattern, src=""):
            conanfile.copy(pattern, dst_folder, src)
        return new_method

    conanfile.copy_headers = wrap(DEFAULT_INCLUDE)
    conanfile.copy_libs = wrap(DEFAULT_LIB)
    conanfile.copy_bins = wrap(DEFAULT_BIN)
    conanfile.copy_res = wrap(DEFAULT_RES)
    try:
        package_output = ScopedOutput("%s package()" % output.scope, output)
        if source_folder != build_folder:
            conanfile.copy = FileCopier(source_folder, package_folder, build_folder)
            with conanfile_exception_formatter(str(conanfile), "package"):
                conanfile.package()
            conanfile.copy.report(package_output, warn=True)
        conanfile.copy = FileCopier(build_folder, package_folder)
        with conanfile_exception_formatter(str(conanfile), "package"):
            conanfile.package()

        conanfile.copy.report(package_output, warn=True)
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

    _create_aux_files(build_folder, package_folder, conanfile)
    output.success("Package '%s' created" % os.path.basename(package_folder))


def _create_aux_files(build_folder, package_folder, conanfile):
    """ auxiliary method that creates CONANINFO and manifest in
    the package_folder
    """

    logger.debug("Creating config files to %s" % package_folder)
    if hasattr(conanfile, "build_id"):
        # It is important to create a new fresh CONANINFO, because for shared
        # build_id folders, the existing one in the build folders is wrong
        save(os.path.join(package_folder, CONANINFO), conanfile.info.dumps())
    else:
        try:
            shutil.copy(os.path.join(build_folder, CONANINFO), package_folder)
        except IOError:
            raise ConanException("%s does not exist inside of your %s folder. "
                                 "Try to re-build it again to solve it."
                                 % (CONANINFO, build_folder))
    # Create the digest for the package
    digest = FileTreeManifest.create(package_folder)
    save(os.path.join(package_folder, CONAN_MANIFEST), str(digest))
