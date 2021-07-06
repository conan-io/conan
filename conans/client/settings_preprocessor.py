from conans.client.build.cppstd_flags import cppstd_flag
from conans.errors import ConanException
from conans.util.log import logger


def preprocess(settings):
    _fill_runtime(settings)
    _check_cppstd(settings)


def _check_cppstd(settings):
    compiler_cppstd = settings.get_safe("compiler.cppstd")

    if not compiler_cppstd:
        return

    compiler = settings.get_safe("compiler")
    if compiler not in ("gcc", "clang", "apple-clang", "Visual Studio"):
        return

    compiler_version = settings.get_safe("compiler.version")
    # Check that we have a flag available for that value of the C++ Standard
    values_range = settings.compiler.cppstd.values_range

    available = [v for v in values_range if cppstd_flag(compiler, compiler_version, v)]
    if compiler_cppstd not in available:
        raise ConanException("The specified 'compiler.cppstd=%s' is not available "
                             "for '%s %s'. Possible values are %s'" % (compiler_cppstd,
                                                                       compiler, compiler_version,
                                                                       available))


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
