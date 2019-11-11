from conans.errors import ConanInvalidConfiguration
from conans.client.build.cppstd_flags import cppstd_flag, cppstd_from_settings
from conans.client.tools.oss import OSInfo


def check_min_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Validate if current cppstd fits the minimal version required.

        In case the current cppstd doesn't fit the minimal version required
        by cppstd, a ConanInvalidConfiguration exception will be raised.

    :param conanfile: ConanFile instance with cppstd to be compared
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17). This option ONLY works on Linux.
    """
    def extract_cpp_version(cppstd):
        return str(cppstd).replace("gnu", "")

    current_cppstd = cppstd_from_settings(conanfile.settings)
    if current_cppstd and gnu_extensions and "gnu" not in current_cppstd and OSInfo().is_linux:
        raise ConanInvalidConfiguration("Current cppstd ({}) does not have GNU extensions, which is"
                                        " required on Linux platform.".format(current_cppstd))
    elif current_cppstd and extract_cpp_version(current_cppstd) < extract_cpp_version(cppstd):
        raise ConanInvalidConfiguration("Current cppstd ({}) is lower than required c++ standard "
                                        "({}).".format(current_cppstd, cppstd))
    else:
        if OSInfo().is_linux and gnu_extensions and "gnu" not in cppstd:
            cppstd = "gnu" + cppstd
        result = cppstd_flag(conanfile.settings.compiler, conanfile.settings.compiler.version,
                             cppstd)
        if not result:
            raise ConanInvalidConfiguration("Current compiler does not support the required "
                                            "c++ standard ({}).".format(cppstd))
        elif OSInfo().is_linux and gnu_extensions and "gnu" not in result:
            raise ConanInvalidConfiguration("Current compiler does not support GNU extensions.")


def valid_minimum_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Validate if current cppstd fits the minimal version required.

    :param conanfile: ConanFile instance with cppstd to be compared
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17). This option ONLY works on Linux.
    :return: True, if current cppstd matches the required cppstd version. Otherwise, False.
    """
    try:
        cppstd_minimum_required(conanfile, cppstd, gnu_extensions)
    except ConanInvalidConfiguration:
        return False
    return True
