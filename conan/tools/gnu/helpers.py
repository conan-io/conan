def is_mingw(conanfile, build_context=False):
    """
    Validates if the current compiler is MinGW (gcc or clang on Windows).

    :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
    :param build_context: If True, will use the settings from the build context, not host ones
    :return: ``bool`` True, if the host compiler is MinGW, otherwise, False.
    """
    if not build_context:
        settings = conanfile.settings
    else:
        settings = conanfile.settings_build

    os_ = settings.get_safe("os")
    compiler = settings.get_safe("compiler")
    return os_ == "Windows" and compiler in ("gcc", "clang")
