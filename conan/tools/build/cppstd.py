from conans.errors import ConanInvalidConfiguration, ConanException
from conans.model.version import Version


def check_min_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Check if current cppstd fits the minimal version required.

        In case the current cppstd doesn't fit the minimal version required
        by cppstd, a ConanInvalidConfiguration exception will be raised.

        1. If settings.compiler.cppstd, the tool will use settings.compiler.cppstd to compare
        2. It not settings.compiler.cppstd, the tool will use compiler to compare (reading the
           default from cppstd_default)
        3. If not settings.compiler is present (not declared in settings) will raise because it
           cannot compare.
        4. If can not detect the default cppstd for settings.compiler, a exception will be raised.

    :param conanfile: The current recipe object. Always use ``self``.
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    """
    if not str(cppstd).isdigit():
        raise ConanException("cppstd parameter must be a number")

    def less_than(lhs, rhs):
        def extract_cpp_version(_cppstd):
            return str(_cppstd).replace("gnu", "")

        def add_millennium(_cppstd):
            return "19%s" % _cppstd if _cppstd == "98" else "20%s" % _cppstd

        lhs = add_millennium(extract_cpp_version(lhs))
        rhs = add_millennium(extract_cpp_version(rhs))
        return lhs < rhs

    current_cppstd = conanfile.settings.get_safe("compiler.cppstd")
    if current_cppstd is None:
        raise ConanInvalidConfiguration("The compiler.cppstd is not defined for this configuration")

    if gnu_extensions and "gnu" not in current_cppstd:
        raise ConanInvalidConfiguration("The cppstd GNU extension is required")

    if less_than(current_cppstd, cppstd):
        raise ConanInvalidConfiguration("Current cppstd ({}) is lower than the required C++ "
                                        "standard ({}).".format(current_cppstd, cppstd))


def valid_min_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Validate if current cppstd fits the minimal version required.

    :param conanfile: The current recipe object. Always use ``self``.
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17). This option ONLY works on Linux.
    :return: True, if current cppstd matches the required cppstd version. Otherwise, False.
    """
    try:
        check_min_cppstd(conanfile, cppstd, gnu_extensions)
    except ConanInvalidConfiguration:
        return False
    return True


def default_cppstd(conanfile, compiler=None, compiler_version=None):
    """
    Get the default ``compiler.cppstd`` for the "conanfile.settings.compiler" and "conanfile
    settings.compiler_version" or for the parameters "compiler" and "compiler_version" if specified.

    :param conanfile: The current recipe object. Always use ``self``.
    :param compiler: Name of the compiler e.g. gcc
    :param compiler_version: Version of the compiler e.g. 12
    :return: The default ``compiler.cppstd`` for the specified compiler
    """
    from conans.client.conf.detect import _cppstd_default
    compiler = compiler or conanfile.settings.get_safe("compiler")
    compiler_version = compiler_version or conanfile.settings.get_safe("compiler.version")
    if not compiler or not compiler_version:
        raise ConanException("Called default_cppstd with no compiler or no compiler.version")
    return _cppstd_default(compiler, Version(compiler_version))


def supported_cppstd(conanfile, compiler=None, compiler_version=None):
    """
    Get the a list of supported ``compiler.cppstd`` for the "conanfile.settings.compiler" and
    "conanfile.settings.compiler_version" or for the parameters "compiler" and "compiler_version"
    if specified.

    :param conanfile: The current recipe object. Always use ``self``.
    :param compiler: Name of the compiler e.g: gcc
    :param compiler_version: Version of the compiler e.g: 12
    :return: a list of supported ``cppstd`` values.
    """
    compiler = compiler or conanfile.settings.get_safe("compiler")
    compiler_version = compiler_version or conanfile.settings.get_safe("compiler.version")
    if not compiler or not compiler_version:
        raise ConanException("Called supported_cppstd with no compiler or no compiler.version")

    func = {"apple-clang": _apple_clang_supported_cppstd,
            "gcc": _gcc_supported_cppstd,
            "msvc": _msvc_supported_cppstd,
            "clang": _clang_supported_cppstd,
            "mcst-lcc": _mcst_lcc_supported_cppstd}.get(compiler)
    if func:
        return func(Version(compiler_version))
    return None


def _apple_clang_supported_cppstd(version):
    """
    ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20"]
    """
    if version < "4.0":
        return []
    if version < "5.1":
        return ["98", "gnu98", "11", "gnu11"]
    if version < "6.1":
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14"]
    if version < "10.0":
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17"]

    return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20"]


def _gcc_supported_cppstd(version):
    """
    ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20", "23", "gnu23"]
    """
    if version < "3.4":
        return []
    if version < "4.3":
        return ["98", "gnu98"]
    if version < "4.8":
        return ["98", "gnu98", "11", "gnu11"]
    if version < "5":
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14"]
    if version < "8":
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17"]
    if version < "11":
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20"]

    return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20", "23", "gnu23"]


def _msvc_supported_cppstd(version):
    """
    [14, 17, 20, 23]
    """
    if version < "190":
        return []
    if version < "191":
        return ["14", "17"]
    if version < "193":
        return ["14", "17", "20"]

    return ["14", "17", "20", "23"]


def _clang_supported_cppstd(version):
    """
    ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20", "23", "gnu23"]
    """
    if version < "2.1":
        return []
    if version < "3.4":
        return ["98", "gnu98", "11", "gnu11"]
    if version < "3.5":
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14"]
    if version < "6":
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17"]
    if version < "12":
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20"]

    return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20", "23", "gnu23"]


def _mcst_lcc_supported_cppstd(version):
    """
    ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20", "23", "gnu23"]
    """

    if version < "1.21":
        return ["98", "gnu98"]
    if version < "1.24":
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14"]
    if version < "1.25":
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17"]

    # FIXME: When cppstd 23 was introduced????

    return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20"]
