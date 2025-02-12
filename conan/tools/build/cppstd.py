import operator

from conan.errors import ConanInvalidConfiguration, ConanException
from conan.internal.api.detect.detect_api import default_cppstd as default_cppstd_
from conan.internal.model.version import Version


def check_min_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Check if current cppstd fits the minimal version required.

        In case the current cppstd doesn't fit the minimal version required
        by cppstd, a ConanInvalidConfiguration exception will be raised.

        settings.compiler.cppstd must be defined, otherwise ConanInvalidConfiguration is raised

    :param conanfile: The current recipe object. Always use ``self``.
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    """
    _check_cppstd(conanfile, cppstd, operator.lt, gnu_extensions)


def check_max_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Check if current cppstd fits the maximum version required.

        In case the current cppstd doesn't fit the maximum version required
        by cppstd, a ConanInvalidConfiguration exception will be raised.

        settings.compiler.cppstd must be defined, otherwise ConanInvalidConfiguration is raised

    :param conanfile: The current recipe object. Always use ``self``.
    :param cppstd: Maximum cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    """
    _check_cppstd(conanfile, cppstd, operator.gt, gnu_extensions)


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


def valid_max_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Validate if current cppstd fits the maximum version required.

    :param conanfile: The current recipe object. Always use ``self``.
    :param cppstd: Maximum cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17). This option ONLY works on Linux.
    :return: True, if current cppstd matches the required cppstd version. Otherwise, False.
    """
    try:
        check_max_cppstd(conanfile, cppstd, gnu_extensions)
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
    compiler = compiler or conanfile.settings.get_safe("compiler")
    compiler_version = compiler_version or conanfile.settings.get_safe("compiler.version")
    if not compiler or not compiler_version:
        raise ConanException("Called default_cppstd with no compiler or no compiler.version")
    return default_cppstd_(compiler, Version(compiler_version))


def supported_cppstd(conanfile, compiler=None, compiler_version=None):
    """
    Get a list of supported ``compiler.cppstd`` for the "conanfile.settings.compiler" and
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
            "mcst-lcc": _mcst_lcc_supported_cppstd,
            "qcc": _qcc_supported_cppstd,
            }.get(compiler)
    if func:
        return func(Version(compiler_version))
    return None


def _check_cppstd(conanfile, cppstd, comparator, gnu_extensions):
    """ Check if current cppstd fits the version required according to a given comparator.

        In case the current cppstd doesn't fit the maximum version required
        by cppstd, a ConanInvalidConfiguration exception will be raised.

        settings.compiler.cppstd must be defined, otherwise ConanInvalidConfiguration is raised

    :param conanfile: The current recipe object. Always use ``self``.
    :param cppstd: Required cppstd version.
    :param comparator: Operator to use to compare the detected and the required cppstd versions.
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    """
    if not str(cppstd).isdigit():
        raise ConanException("cppstd parameter must be a number")

    def compare(lhs, rhs, comp):
        def extract_cpp_version(_cppstd):
            return str(_cppstd).replace("gnu", "")

        def add_millennium(_cppstd):
            return "19%s" % _cppstd if _cppstd == "98" else "20%s" % _cppstd

        lhs = add_millennium(extract_cpp_version(lhs))
        rhs = add_millennium(extract_cpp_version(rhs))
        return not comp(lhs, rhs)

    current_cppstd = conanfile.settings.get_safe("compiler.cppstd")
    if current_cppstd is None:
        raise ConanInvalidConfiguration("The compiler.cppstd is not defined for this configuration")

    if gnu_extensions and "gnu" not in current_cppstd:
        raise ConanInvalidConfiguration("The cppstd GNU extension is required")

    if not compare(current_cppstd, cppstd, comparator):
        raise ConanInvalidConfiguration(
            "Current cppstd ({}) is {} than the required C++ standard ({}).".format(
                current_cppstd, "higher" if comparator == operator.gt else "lower", cppstd))


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
    if version < "13.0":
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20"]
    # https://github.com/conan-io/conan/pull/17092 doesn't show c++23 full support until 16
    # but it was this before Conan 2.9, so keeping it to not break
    if version < "16.0":
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20",
                "23", "gnu23"]

    return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20", "23", "gnu23",
            "26", "gnu26"]


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
    # https://github.com/conan-io/conan/pull/17092
    if version < "14.0":
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20",
                "23", "gnu23"]

    return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20", "23", "gnu23",
            "26", "gnu26"]


def _msvc_supported_cppstd(version):
    """
    https://learn.microsoft.com/en-us/cpp/build/reference/std-specify-language-standard-version?view=msvc-170
    - /std:c++14 starting in Visual Studio 2015 Update 3 (190)
    - /std:c++17 starting in Visual Studio 2017 version 15.3. (191)
    - /std:c++20 starting in Visual Studio 2019 version 16.11 (192)
    [14, 17, 20, 23]
    """
    if version < "190":  # pre VS 2015
        return []
    if version < "191":  # VS 2015
        return ["14"]
    if version < "192":  # VS 2017
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
    # https://github.com/conan-io/conan/pull/17092
    if version < "17.0":
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20",
                "23", "gnu23"]
    return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17", "20", "gnu20", "23", "gnu23",
            "26", "gnu26"]


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


def _qcc_supported_cppstd(version):
    """
    [98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17]
    """

    if version < "5":
        return ["98", "gnu98"]
    else:
        return ["98", "gnu98", "11", "gnu11", "14", "gnu14", "17", "gnu17"]
