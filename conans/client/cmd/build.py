import os

from conans.client.output import ScopedOutput
from conans.util.log import logger
from conans.errors import (NotFoundException, ConanException,
                           conanfile_exception_formatter)
from conans.paths import CONANFILE, CONANFILE_TXT
from conans.util.files import mkdir
from conans.model.conan_file import get_env_context_manager


def build(graph_manager, hook_manager, conanfile_path, output,
          source_folder, build_folder, package_folder, install_folder,
          test=False, should_configure=True, should_build=True, should_install=True,
          should_test=True):
    """ Call to build() method saved on the conanfile.py
    param conanfile_path: path to a conanfile.py
    """
    logger.debug("Building in %s" % build_folder)
    logger.debug("Conanfile in %s" % conanfile_path)

    try:
        # Append env_vars to execution environment and clear when block code ends
        output = ScopedOutput(("%s (test package)" % test) if test else "Project",
                              output)
        conan_file = graph_manager.load_consumer_conanfile(conanfile_path, install_folder,
                                                           output, deps_info_required=True)
    except NotFoundException:
        # TODO: Auto generate conanfile from requirements file
        raise ConanException("'%s' file is needed for build.\n"
                             "Create a '%s' and move manually the "
                             "requirements and generators from '%s' file"
                             % (CONANFILE, CONANFILE, CONANFILE_TXT))

    if test:
        try:
            conan_file.requires.add(test)
        except ConanException:
            pass

    conan_file.should_configure = should_configure
    conan_file.should_build = should_build
    conan_file.should_install = should_install
    conan_file.should_test = should_test

    try:
        mkdir(build_folder)
        os.chdir(build_folder)
        conan_file.build_folder = build_folder
        conan_file.source_folder = source_folder
        conan_file.package_folder = package_folder
        conan_file.install_folder = install_folder
        hook_manager.execute("pre_build", conanfile=conan_file,
                             conanfile_path=conanfile_path)
        with get_env_context_manager(conan_file):
            output.highlight("Running build()")
            with conanfile_exception_formatter(str(conan_file), "build"):
                conan_file.build()
            hook_manager.execute("post_build", conanfile=conan_file,
                                 conanfile_path=conanfile_path)
            if test:
                output.highlight("Running test()")
                with conanfile_exception_formatter(str(conan_file), "test"):
                    conan_file.test()
    except ConanException:
        raise  # Raise but not let to reach the Exception except (not print traceback)
    except Exception:
        import traceback
        trace = traceback.format_exc().split('\n')
        raise ConanException("Unable to build it successfully\n%s" % '\n'.join(trace[3:]))
