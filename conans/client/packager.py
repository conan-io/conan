from conans.util.files import mkdir, save, rmdir
import os
from conans.util.log import logger
from conans.paths import CONANINFO, CONAN_MANIFEST
from conans.errors import ConanException
from conans.model.build_info import DEFAULT_RES, DEFAULT_BIN, DEFAULT_LIB, DEFAULT_INCLUDE
import shutil
from conans.client.file_copier import FileCopier
from conans.model.manifest import FileTreeManifest
from conans.client.output import ScopedOutput


def create_package(conanfile, build_folder, package_folder, output):
    """ copies built artifacts, libs, headers, data, etc from build_folder to
    package folder
    """
    mkdir(package_folder)

    # Make the copy of all the patterns
    output.info("Generating the package")
    output.info("Package folder %s" % (package_folder))
    conanfile.copy = FileCopier(build_folder, package_folder)

    def wrap(dst_folder):
        def new_method(pattern, src=""):
            conanfile.copy(pattern, dst_folder, src)
        return new_method

    conanfile.copy_headers = wrap(DEFAULT_INCLUDE)
    conanfile.copy_libs = wrap(DEFAULT_LIB)
    conanfile.copy_bins = wrap(DEFAULT_BIN)
    conanfile.copy_res = wrap(DEFAULT_RES)
    try:
        conanfile.package_folder = package_folder
        conanfile.package()
        package_output = ScopedOutput("%s package()" % output.scope, output)
        conanfile.copy.report(package_output, warn=True)
    except Exception as e:
        os.chdir(build_folder)
        try:
            rmdir(package_folder)
        except Exception as e_rm:
            output.error("Unable to remove package folder %s\n%s"
                                    % (package_folder, str(e_rm)))
            output.warn("**** Please delete it manually ****")
        raise ConanException("%s: %s" % (conanfile.name, str(e)))

    _create_aux_files(build_folder, package_folder)
    output.success("Package '%s' created" % os.path.basename(package_folder))


def generate_manifest(package_folder):
    # Create the digest for the package
    digest = FileTreeManifest.create(package_folder)
    save(os.path.join(package_folder, CONAN_MANIFEST), str(digest))


def _create_aux_files(build_folder, package_folder):
    """ auxiliary method that creates CONANINFO in
    the package_folder
    """
    try:
        logger.debug("Creating config files to %s" % package_folder)
        shutil.copy(os.path.join(build_folder, CONANINFO), package_folder)

        # Create the digest for the package
        generate_manifest(package_folder)

    except IOError:
        raise ConanException("%s does not exist inside of your %s folder. Try to re-build it again"
                             " to solve it." % (CONANINFO, build_folder))
