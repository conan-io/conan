import operator

from conan.errors import ConanInvalidConfiguration, ConanException
from conans.model.version import Version


def check_min_cstd(conanfile, cstd, gnu_extensions=False):
    """ Check if current cstd fits the minimal version required.

        In case the current cstd doesn't fit the minimal version required
        by cstd, a ConanInvalidConfiguration exception will be raised.

        1. If settings.compiler.cstd, the tool will use settings.compiler.cstd to compare
        2. It not settings.compiler.cstd, the tool will use compiler to compare (reading the
           default from cstd_default)
        3. If not settings.compiler is present (not declared in settings) will raise because it
           cannot compare.
        4. If can not detect the default cstd for settings.compiler, a exception will be raised.

    :param conanfile: The current recipe object. Always use ``self``.
    :param cstd: Minimal cstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    """
    _check_cstd(conanfile, cstd, operator.lt, gnu_extensions)


def check_max_cstd(conanfile, cstd, gnu_extensions=False):
    """ Check if current cstd fits the maximum version required.

        In case the current cstd doesn't fit the maximum version required
        by cstd, a ConanInvalidConfiguration exception will be raised.

        1. If settings.compiler.cstd, the tool will use settings.compiler.cstd to compare
        2. It not settings.compiler.cstd, the tool will use compiler to compare (reading the
           default from cstd_default)
        3. If not settings.compiler is present (not declared in settings) will raise because it
           cannot compare.
        4. If can not detect the default cstd for settings.compiler, a exception will be raised.

    :param conanfile: The current recipe object. Always use ``self``.
    :param cstd: Maximum cstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    """
    _check_cstd(conanfile, cstd, operator.gt, gnu_extensions)


def valid_min_cstd(conanfile, cstd, gnu_extensions=False):
    """ Validate if current cstd fits the minimal version required.

    :param conanfile: The current recipe object. Always use ``self``.
    :param cstd: Minimal cstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17). This option ONLY works on Linux.
    :return: True, if current cstd matches the required cstd version. Otherwise, False.
    """
    try:
        check_min_cstd(conanfile, cstd, gnu_extensions)
    except ConanInvalidConfiguration:
        return False
    return True


def valid_max_cstd(conanfile, cstd, gnu_extensions=False):
    """ Validate if current cstd fits the maximum version required.

    :param conanfile: The current recipe object. Always use ``self``.
    :param cstd: Maximum cstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17). This option ONLY works on Linux.
    :return: True, if current cstd matches the required cstd version. Otherwise, False.
    """
    try:
        check_max_cstd(conanfile, cstd, gnu_extensions)
    except ConanInvalidConfiguration:
        return False
    return True


def supported_cstd(conanfile, compiler=None, compiler_version=None):
    """
    Get a list of supported ``compiler.cstd`` for the "conanfile.settings.compiler" and
    "conanfile.settings.compiler_version" or for the parameters "compiler" and "compiler_version"
    if specified.

    :param conanfile: The current recipe object. Always use ``self``.
    :param compiler: Name of the compiler e.g: gcc
    :param compiler_version: Version of the compiler e.g: 12
    :return: a list of supported ``cstd`` values.
    """
    compiler = compiler or conanfile.settings.get_safe("compiler")
    compiler_version = compiler_version or conanfile.settings.get_safe("compiler.version")
    if not compiler or not compiler_version:
        raise ConanException("Called supported_cstd with no compiler or no compiler.version")

    func = {"apple-clang": _apple_clang_supported_cstd,
            "gcc": _gcc_supported_cstd,
            "msvc": _msvc_supported_cstd,
            "clang": _clang_supported_cstd,
            }.get(compiler)
    if func:
        return func(Version(compiler_version))
    return None


def _check_cstd(conanfile, cstd, comparator, gnu_extensions):
    """ Check if current cstd fits the version required according to a given comparator.

        In case the current cstd doesn't fit the maximum version required
        by cstd, a ConanInvalidConfiguration exception will be raised.

        1. If settings.compiler.cstd, the tool will use settings.compiler.cstd to compare
        2. It not settings.compiler.cstd, the tool will use compiler to compare (reading the
           default from cstd_default)
        3. If not settings.compiler is present (not declared in settings) will raise because it
           cannot compare.
        4. If can not detect the default cstd for settings.compiler, a exception will be raised.

    :param conanfile: The current recipe object. Always use ``self``.
    :param cstd: Required cstd version.
    :param comparator: Operator to use to compare the detected and the required cstd versions.
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    """
    if not str(cstd).isdigit():
        raise ConanException("cstd parameter must be a number")

    def compare(lhs, rhs, comp):
        def extract_cpp_version(_cstd):
            return str(_cstd).replace("gnu", "")

        def add_millennium(_cstd):
            return "19%s" % _cstd if _cstd == "99" else "20%s" % _cstd

        lhs = add_millennium(extract_cpp_version(lhs))
        rhs = add_millennium(extract_cpp_version(rhs))
        return not comp(lhs, rhs)

    current_cstd = conanfile.settings.get_safe("compiler.cstd")
    if current_cstd is None:
        raise ConanInvalidConfiguration("The compiler.cstd is not defined for this configuration")

    if gnu_extensions and "gnu" not in current_cstd:
        raise ConanInvalidConfiguration("The cstd GNU extension is required")

    if not compare(current_cstd, cstd, comparator):
        raise ConanInvalidConfiguration(
            "Current cstd ({}) is {} than the required C standard ({}).".format(
                current_cstd, "higher" if comparator == operator.gt else "lower", cstd))


def _apple_clang_supported_cstd(version):
    # TODO: Per-version support
    return ["99", "gnu99", "11", "gnu11", "17", "gnu17", "23", "gnu23"]


def _gcc_supported_cstd(version):
    if version < "4.7":
        return ["99", "gnu99"]
    if version < "8":
        return ["99", "gnu99", "11", "gnu11"]
    if version < "14":
        return ["99", "gnu99", "11", "gnu11", "17", "gnu17"]
    return ["99", "gnu99", "11", "gnu11", "17", "gnu17", "23", "gnu23"]


def _msvc_supported_cstd(version):
    if version < "192":
        return []
    return ["11", "17"]


def _clang_supported_cstd(version):
    if version < "3":
        return ["99", "gnu99"]
    if version < "6":
        return ["99", "gnu99", "11", "gnu11"]
    if version < "18":
        return ["99", "gnu99", "11", "gnu11", "17", "gnu17"]
    return ["99", "gnu99", "11", "gnu11", "17", "gnu17", "23", "gnu23"]
