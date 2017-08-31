from conans.util.log import logger


def preprocess(settings):
    fill_runtime(settings)


def fill_runtime(settings):
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
