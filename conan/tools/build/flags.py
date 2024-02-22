from conan.tools._compilers import cppstd_flag as cppstd_flag_settings


def cppstd_flag(conanfile):
    """
    Returns flags specific to the C++ standard based on the ``conanfile.settings.compiler``,
    ``conanfile.settings.compiler.version`` and ``conanfile.settings.compiler.cppstd``.
    It also considers when using GNU extension in ``settings.compiler.cppstd``, reflecting it in the
    compiler flag. Currently, it supports GCC, Clang, AppleClang, MSVC, Intel, MCST-LCC.
    In case there is no ``settings.compiler`` or ``settings.cppstd`` in the profile, the result will
    be an **empty string**.
    :param conanfile: The current recipe object. Always use ``self``.
    :return: ``str`` with the standard C++ flag used by the compiler. e.g. "-std=c++11", "/std:c++latest"
    """
    settings = conanfile.settings
    return cppstd_flag_settings(settings)
