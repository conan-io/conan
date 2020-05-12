from conans.errors import (conanfile_exception_formatter)
from conans.model.conan_file import get_env_context_manager
from conans.util.conan_v2_mode import conan_v2_behavior


def run_configure_method(conanfile, down_options, down_ref, ref):
    """ Run all the config-related functions for the given conanfile object """

    # Avoid extra time manipulating the sys.path for python
    with get_env_context_manager(conanfile, without_python=True):
        if hasattr(conanfile, "config"):
            conan_v2_behavior("config() has been deprecated. "
                              "Use config_options() and configure()",
                              v1_behavior=conanfile.output.warn)
            with conanfile_exception_formatter(str(conanfile), "config"):
                conanfile.config()

        with conanfile_exception_formatter(str(conanfile), "config_options"):
            conanfile.config_options()

        conanfile.options.propagate_upstream(down_options, down_ref, ref)

        if hasattr(conanfile, "config"):
            with conanfile_exception_formatter(str(conanfile), "config"):
                conanfile.config()

        with conanfile_exception_formatter(str(conanfile), "configure"):
            conanfile.configure()

        conanfile.settings.validate()  # All has to be ok!
        conanfile.options.validate()
