def is_mingw(conanfile, build_context=False):
    """
    Validate if the current compiler is a MinGW toolchain (host context by default).

    A MinGW toolchain is detected by the following Conan settings:

    - ``os == "Windows"`` (a non-Windows host is never MinGW)
    - ``os.subsystem != "cygwin"`` (Cygwin uses a POSIX layer, not MinGW)
    - ``compiler == "gcc"``, OR
      ``compiler == "clang"`` with ``compiler.runtime`` unset (MinGW Clang).
      ``clang-cl`` is detected via ``compiler.runtime`` and is not considered MinGW.

    Reference:
    https://blog.conan.io/2022/10/13/Different-flavors-Clang-compiler-Windows.html

    :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
    :param build_context: If True, will use the settings from the build context, not host ones.
    :return: ``bool`` True if the selected context targets a MinGW toolchain, otherwise False.
    """
    settings = conanfile.settings_build if build_context else conanfile.settings
    if settings.get_safe("os") != "Windows":
        return False
    if settings.get_safe("os.subsystem") == "cygwin":
        return False
    compiler = settings.get_safe("compiler")
    if compiler == "gcc":
        return True
    if compiler == "clang" and settings.get_safe("compiler.runtime") is None:
        return True
    return False
