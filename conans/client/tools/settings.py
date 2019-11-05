from conans.errors import ConanInvalidConfiguration
from conans.client.build.cppstd_flags import cppstd_flag, cppstd_from_settings


def cppstd_minimum_required(conanfile, cppstd_version):
    """ Validate if current cppstd fits the minimal version required.

        In case cppstd_version doesn't fit the minimal version, a
        ConanInvalidConfiguration exception will be raised.

    :param conanfile: ConanFile instance with cppstd
    :param cppstd_version: Minimal cppstd version required
    """
    def extract_cpp_version(cppstd):
        return int(str(cppstd).replace("gnu", ""))

    cppstd = cppstd_from_settings(conanfile.settings)
    if cppstd and extract_cpp_version(cppstd) < extract_cpp_version(cppstd_version):
        raise ConanInvalidConfiguration("Current cppstd ({}) is lower than required c++ standard "
                                        "({}).".format(cppstd, cppstd_version))
    elif not cppstd_flag(conanfile.settings.compiler, conanfile.settings.compiler.version,
                         cppstd_version):
        raise ConanInvalidConfiguration("Current compiler does not not support the required "
                                        "c++ standard ({}).".format(cppstd_version))
