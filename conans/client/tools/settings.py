from conans.errors import ConanInvalidConfiguration, ConanException
from conans.client.build.cppstd_flags import cppstd_flag, cppstd_from_settings
from conans.client.tools.oss import OSInfo


def check_min_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Check if current cppstd fits the minimal version required.

        In case the current cppstd doesn't fit the minimal version required
        by cppstd, a ConanInvalidConfiguration exception will be raised.

    :param conanfile: ConanFile instance with cppstd to be compared
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17). This option ONLY works on Linux.
    """
    if not cppstd:
        raise ConanException("Cannot check invalid cppstd version")
    if not conanfile:
        raise ConanException("conanfile must be a ConanFile object")
    if not str(cppstd).isdigit():
        raise ConanException("cppstd must be a number")

    def less_than(lhs, rhs):
        def extract_cpp_version(cppstd):
            return str(cppstd).replace("gnu", "")

        def add_millennium(cppstd):
            return "19%s" % cppstd if cppstd == "98" else "20%s" % cppstd

        lhs = add_millennium(extract_cpp_version(lhs))
        rhs = add_millennium(extract_cpp_version(rhs))
        return lhs < rhs

    def is_linux(conanfile):
        os = conanfile.settings.get_safe("os_build")
        if os is not None:
            return os == "Linux"
        return OSInfo().is_linux

    current_cppstd = cppstd_from_settings(conanfile.settings)
    if current_cppstd and gnu_extensions and "gnu" not in current_cppstd and is_linux(conanfile):
        raise ConanInvalidConfiguration("Current cppstd ({}) does not have GNU extensions, which is"
                                        " required on Linux platform.".format(current_cppstd))
    elif current_cppstd and less_than(current_cppstd, cppstd):
        raise ConanInvalidConfiguration("Current cppstd ({}) is lower than required C++ standard "
                                        "({}).".format(current_cppstd, cppstd))
    else:
        if OSInfo().is_linux and gnu_extensions and "gnu" not in cppstd:
            cppstd = "gnu" + cppstd
        result = cppstd_flag(conanfile.settings.get_safe("compiler"),
                             conanfile.settings.get_safe("compiler.version"),
                             cppstd)
        if not result:
            raise ConanInvalidConfiguration("Current compiler does not support the required "
                                            "C++ standard ({}).".format(cppstd))
        elif OSInfo().is_linux and gnu_extensions and "gnu" not in result:
            raise ConanInvalidConfiguration("Current compiler does not support GNU extensions.")


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
