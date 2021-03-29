import os

from conan.tools._compilers import use_win_mingw
from conans.errors import ConanException


def is_multi_configuration(generator):
    if not generator:
        return False
    return "Visual" in generator or "Xcode" in generator


def get_generator(conanfile):
    # Returns the name of the generator to be used by CMake
    if "CONAN_CMAKE_GENERATOR" in os.environ:
        return os.environ["CONAN_CMAKE_GENERATOR"]

    compiler = conanfile.settings.get_safe("compiler")
    compiler_version = conanfile.settings.get_safe("compiler.version")

    if compiler == "msvc":
        if compiler_version is None:
            raise ConanException("compiler.version must be defined")
        version = compiler_version[:4]  # Remove the latest version number 19.1X if existing
        try:
            _visuals = {'19.0': '14 2015',
                        '19.1': '15 2017',
                        '19.2': '16 2019'}[version]
        except KeyError:
            raise ConanException("compiler.version '{}' doesn't map "
                                 "to a known VS version".format(version))
        base = "Visual Studio %s" % _visuals
        return base

    compiler_base = conanfile.settings.get_safe("compiler.base")
    compiler_base_version = conanfile.settings.get_safe("compiler.base.version")

    if compiler == "Visual Studio" or compiler_base == "Visual Studio":
        version = compiler_base_version or compiler_version
        major_version = version.split('.', 1)[0]
        _visuals = {'8': '8 2005',
                    '9': '9 2008',
                    '10': '10 2010',
                    '11': '11 2012',
                    '12': '12 2013',
                    '14': '14 2015',
                    '15': '15 2017',
                    '16': '16 2019'}.get(major_version, "UnknownVersion %s" % version)
        base = "Visual Studio %s" % _visuals
        return base

    if use_win_mingw(conanfile):
        return "MinGW Makefiles"

    return "Unix Makefiles"
