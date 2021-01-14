from conans.client.build.cppstd_flags import cppstd_flag
from conans.errors import ConanException
from conans.util.conan_v2_mode import conan_v2_behavior
from conans.util.log import logger


def preprocess(settings):
    _fill_runtime(settings)
    _check_cppstd(settings)


def _check_cppstd(settings):
    compiler = settings.get_safe("compiler")
    compiler_version = settings.get_safe("compiler.version")
    cppstd = settings.get_safe("cppstd")
    compiler_cppstd = settings.get_safe("compiler.cppstd")

    if compiler == "msvc":
        # This is hardcoded at the moment, because the minimum defined version is 19.0, with c++14
        # TODO: When older versions of msvc are defined in settings, cppstd can be None
        if compiler_cppstd is None:
            raise ConanException("compiler.cppstd is not defined for 'msvc' compiler. The minimum "
                                 "and compiler version default is 'compiler.cppstd=14'")
        return

    if not cppstd and not compiler_cppstd:
        return

    # Checks: one or the other, but not both
    if cppstd and compiler_cppstd:
        raise ConanException("Do not use settings 'compiler.cppstd' together with 'cppstd'."
                             " Use only the former one.")

    if cppstd:
        conan_v2_behavior("Setting 'cppstd' is deprecated in favor of 'compiler.cppstd'")

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
                runtime = "MDd" if settings.get_safe("build_type") == "Debug" else "MD"
                settings.compiler.runtime = runtime
                msg = "Setting 'compiler.runtime' not declared, automatically adjusted to '%s'"
                logger.info(msg % runtime)
        elif settings.compiler == "intel" and settings.get_safe("compiler.base") == "Visual Studio":
            if settings.get_safe("compiler.base.runtime") is None:
                runtime = "MDd" if settings.get_safe("build_type") == "Debug" else "MD"
                settings.compiler.base.runtime = runtime
                msg = "Setting 'compiler.base.runtime' not declared, automatically adjusted to '%s'"
                logger.info(msg % runtime)
        elif settings.compiler == "msvc":
            if settings.get_safe("compiler.runtime_type") is None:
                runtime = "Debug" if settings.get_safe("build_type") == "Debug" else "Release"
                settings.compiler.runtime_type = runtime
    except Exception:  # If the settings structure doesn't match these general
        # asumptions, like unexistant runtime
        pass
