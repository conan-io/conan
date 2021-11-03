import os

from conans.client.conanfile.build import run_build_method
from conans.client.tools import chdir
from conans.client.tools import no_op
from conans.errors import (ConanException, conanfile_exception_formatter)
from conans.util.files import mkdir
from conans.util.log import logger


def cmd_build(app, conanfile_path, conan_file, base_path, source_folder, build_folder,
              package_folder, install_folder, test=False):
    """ Call to build() method saved on the conanfile.py
    param conanfile_path: path to a conanfile.py
    """
    logger.debug("BUILD: folder '%s'" % build_folder)
    logger.debug("BUILD: Conanfile at '%s'" % conanfile_path)

    if test:
        try:
            # TODO: check what to do with this, should be removed?
            conan_file.requires(repr(test))
        except ConanException:
            pass

    try:
        # FIXME: Conan 2.0 all these build_folder, source_folder will disappear
        #  Only base_path and conanfile_path will remain
        if hasattr(conan_file, "layout"):
            conanfile_folder = os.path.dirname(conanfile_path)
            conan_file.folders.set_base_build(conanfile_folder)
            conan_file.folders.set_base_source(conanfile_folder)
            conan_file.folders.set_base_package(conanfile_folder)
            conan_file.folders.set_base_generators(conanfile_folder)
            conan_file.folders.set_base_install(conanfile_folder)
        else:
            conan_file.folders.set_base_build(build_folder)
            conan_file.folders.set_base_source(source_folder)
            conan_file.folders.set_base_package(package_folder)
            conan_file.folders.set_base_generators(base_path)
            conan_file.folders.set_base_install(install_folder)

        mkdir(conan_file.build_folder)
        with chdir(conan_file.build_folder):
            run_build_method(conan_file, app.hook_manager, conanfile_path=conanfile_path)

        if test:
            with no_op():  # TODO: Remove this in a later refactor
                conan_file.output.highlight("Running test()")
                with conanfile_exception_formatter(str(conan_file), "test"):
                    with chdir(conan_file.build_folder):
                        conan_file.test()

    except ConanException:
        raise  # Raise but not let to reach the Exception except (not print traceback)
    except Exception:
        import traceback
        trace = traceback.format_exc().split('\n')
        raise ConanException("Unable to build it successfully\n%s" % '\n'.join(trace[3:]))
