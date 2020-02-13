from conans.client.build.cppstd_flags import cppstd_default
from conans.errors import ConanInvalidConfiguration, ConanException


def check_min_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Check if current cppstd fits the minimal version required.

        In case the current cppstd doesn't fit the minimal version required
        by cppstd, a ConanInvalidConfiguration exception will be raised.

        1. If settings.compiler.cppstd, the tool will use settings.compiler.cppstd to compare
        2. It not settings.compiler.cppstd, the tool will use compiler to compare (reading the
           default from cppstd_default)
        3. If not settings.compiler is present (not declared in settings) will raise because it
           cannot compare.

    :param conanfile: ConanFile instance with cppstd to be compared
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

    def check_required_gnu_extension(_cppstd):
        if gnu_extensions and "gnu" not in _cppstd:
            raise ConanInvalidConfiguration("The cppstd GNU extension is required")

    def deduced_cppstd():
        cppstd = conanfile.settings.get_safe("compiler.cppstd")
        if cppstd:
            return cppstd

        compiler = conanfile.settings.get_safe("compiler")
        compiler_version = conanfile.settings.get_safe("compiler.version")
        if not compiler or not compiler_version:
            raise ConanException("Could not obtain cppstd because there is no declared "
                                 "compiler in the 'settings' field of the recipe.")
        return cppstd_default(compiler, compiler_version)

    current_cppstd = deduced_cppstd()
    check_required_gnu_extension(current_cppstd)

    if less_than(current_cppstd, cppstd):
        raise ConanInvalidConfiguration("Current cppstd ({}) is lower than the required C++ "
                                        "standard ({}).".format(current_cppstd, cppstd))


def valid_min_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Validate if current cppstd fits the minimal version required.

    :param conanfile: ConanFile instance with cppstd to be compared
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17). This option ONLY works on Linux.
    :return: True, if current cppstd matches the required cppstd version. Otherwise, False.
    """
    try:
        check_min_cppstd(conanfile, cppstd, gnu_extensions)
    except ConanInvalidConfiguration:
        return False
    return True
