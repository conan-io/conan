from conans.errors import ConanInvalidConfiguration
from conans.client.build.cppstd_flags import cppstd_flag, cppstd_from_settings


def cppstd_minimum_required(conanfile, cppstd_version):
    cppstd = cppstd_from_settings(conanfile.settings)
    if cppstd and str(conanfile.settings.compiler.cppstd) < cppstd_version:
        raise ConanInvalidConfiguration("Current cppstd ({}) is lower than required c++ standard "
                                        "({}).".format(cppstd, cppstd_version))
    elif not cppstd_flag(conanfile.settings.compiler, conanfile.settings.compiler.version,
                         cppstd_version):
        raise ConanInvalidConfiguration("Current compiler does not not support the required "
                                        "c++ standard ({}).".format(cppstd_version))
