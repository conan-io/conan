import warnings

from conans.client.build.cppstd_flags import cppstd_flag
from conans.errors import ConanException
from conans.util.log import logger


def preprocess(settings):
    _fill_runtime(settings)
    _check_cppstd(settings)
    _check_xbuild(settings)


def _check_xbuild(settings):
    os_build = settings.get_safe("os_build")
    arch_build = settings.get_safe("arch_build")

    if os_build or arch_build:
        warnings.warn("Settings 'os_build' and 'arch_build' are deprecated in favor of the new"
                      " cross-compiling model. Please, refer to the docs and"
                      " actualize your recipe.")

    os_target = settings.get_safe("os_target")
    arch_target = settings.get_safe("arch_target")

    if os_target or arch_target:
        warnings.warn("Settings 'os_target' and 'arch_target' are deprecated in favor of the new"
                      " cross-compiling model. Please, refer to the docs and"
                      " actualize your recipe.")


def _check_cppstd(settings):
    compiler = settings.get_safe("compiler")
    compiler_version = settings.get_safe("compiler.version")
    cppstd = settings.get_safe("cppstd")
    compiler_cppstd = settings.get_safe("compiler.cppstd")

    if not cppstd and not compiler_cppstd:
        return

    # Checks: one or the other, but not both
    if cppstd and compiler_cppstd:
        raise ConanException("Do not use settings 'compiler.cppstd' together with 'cppstd'."
                             " Use only the former one.")

    if cppstd:
        warnings.warn("Setting 'cppstd' is deprecated in favor of 'compiler.cppstd'")

    if compiler not in ("gcc", "clang", "apple-clang", "Visual Studio"):
        return

    # Check that we have a flag available for that value of the C++ Standard
    def check_flag_available(values_range, value, setting_id):
        available = [v for v in values_range if cppstd_flag(compiler, compiler_version, v)]
        if str(value) not in available:
            raise ConanException("The specified '%s=%s' is not available "
                                 "for '%s %s'. Possible values are %s'" % (setting_id,
                                                                           value,
                                                                           compiler,
                                                                           compiler_version,
                                                                           available))

    if cppstd:
        check_flag_available(settings.cppstd.values_range, cppstd, "cppstd")
    else:
        check_flag_available(settings.compiler.cppstd.values_range,
                             compiler_cppstd, "compiler.cppstd")


def _fill_runtime(settings):
    try:
        if settings.compiler == "Visual Studio":
            if settings.get_safe("compiler.runtime") is None:
                settings.compiler.runtime = "MDd" if settings.get_safe("build_type") == "Debug" \
                                                  else "MD"
                logger.info("Setting 'compiler.runtime' not declared, automatically "
                            "adjusted to '%s'" % settings.compiler.runtime)
    except Exception:  # If the settings structure doesn't match these general
        # asumptions, like unexistant runtime
        pass
