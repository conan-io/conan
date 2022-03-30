from conans.errors import conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager
from conans.util.conan_v2_mode import conan_v2_error
from conans.util.misc import make_tuple


def run_configure_method(conanfile, down_options, down_ref, ref):
    """ Run all the config-related functions for the given conanfile object """

    # Avoid extra time manipulating the sys.path for python
    with get_env_context_manager(conanfile, without_python=True):
        if hasattr(conanfile, "config"):
            conan_v2_error("config() has been deprecated. Use config_options() and configure()")
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
        # Recipe provides its own name if nothing else is defined
        conanfile.provides = make_tuple(conanfile.provides or conanfile.name)

        if conanfile.deprecated:
            from six import string_types
            message = "Recipe '%s' is deprecated" % conanfile.display_name
            if isinstance(conanfile.deprecated, string_types):
                message += " in favor of '%s'" % conanfile.deprecated
            message += ". Please, consider changing your requirements."
            conanfile.output.warn(message)

        # Once the node is configured call the layout()
        if hasattr(conanfile, "layout"):
            with conanfile_exception_formatter(str(conanfile), "layout"):
                conanfile.layout()
