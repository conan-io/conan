from conans.util.log import logger


def preprocess(settings):
    _fill_runtime(settings)
    # Check cppstd doesn't need to be harcoded in Conan, instead it should
    # probably be hook-like code, user side (and opt-in/opt-out)


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
