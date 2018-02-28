from conans.client.build.cppstd_flags import available_cppstd_versions
from conans.errors import ConanException
from conans.util.log import logger


def preprocess(settings):
    fill_runtime(settings)
    check_cppstd(settings)


def check_cppstd(settings):
    compiler = settings.get_safe("compiler")
    compiler_version = settings.get_safe("compiler.version")
    cppstd = settings.get_safe("cppstd")

    if not cppstd or not compiler or not compiler_version:
        return
    available = available_cppstd_versions(compiler, compiler_version)
    if str(cppstd) not in available:
        raise ConanException("The specified 'cppstd=%s' is not available "
                             "for '%s %s'. Possible values are %s'" % (cppstd,
                                                                      compiler,
                                                                      compiler_version,
                                                                      available))


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
