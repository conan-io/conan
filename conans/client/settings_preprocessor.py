import warnings

from conans.client.build.cppstd_flags import cppstd_flag
from conans.errors import ConanException
from conans.util.log import logger


def preprocess(settings):
    fill_runtime(settings)
    check_cppstd(settings)


def check_cppstd(settings):
    compiler = settings.get_safe("compiler")
    compiler_version = settings.get_safe("compiler.version")
    cppstd = settings.get_safe("cppstd")
    compiler_cppstd = settings.get_safe("compiler.cppstd")

    if not cppstd and not compiler_cppstd:
        # TODO: Why not add the default one?
        return

    # Checks: one or the other, but not both
    if cppstd and compiler_cppstd:
        raise ConanException("Do not use settings 'compiler.cppstd' together with 'cppstd'."
                             " Use only the former one.")

    if cppstd:
        warnings.warn("Setting 'cppstd' is deprecated in favor of 'compiler.cppstd'")

    if compiler not in ("gcc", "clang", "apple-clang", "Visual Studio"):
        return

    if cppstd:
        cppstd_values = settings.cppstd.values_range
        available = [v for v in cppstd_values if cppstd_flag(compiler, compiler_version, v)]
        if str(cppstd) not in available:
            raise ConanException("The specified 'cppstd=%s' is not available "
                                 "for '%s %s'. Possible values are %s'" % (cppstd,
                                                                           compiler,
                                                                           compiler_version,
                                                                           available))
    else:
        cppstd_values = settings.compiler.cppstd.values_range
        available = [v for v in cppstd_values if cppstd_flag(compiler, compiler_version, v)]
        if str(compiler_cppstd) not in available:
            raise ConanException("The specified 'compiler.cppstd=%s' is not available "
                                 "for '%s %s'. Possible values are %s'" % (compiler_cppstd,
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
