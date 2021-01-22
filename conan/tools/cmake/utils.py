import os

from conans.errors import ConanException
from conans.util.log import logger


def is_multi_configuration(generator):
    if not generator:
        return False
    return "Visual" in generator or "Xcode" in generator


def architecture_flag(settings):
    """
    returns flags specific to the target architecture and compiler
    """
    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    arch = settings.get_safe("arch")
    the_os = settings.get_safe("os")
    if not compiler or not arch:
        return ""

    if str(compiler) in ['gcc', 'apple-clang', 'clang', 'sun-cc']:
        if str(arch) in ['x86_64', 'sparcv9', 's390x']:
            return '-m64'
        elif str(arch) in ['x86', 'sparc']:
            return '-m32'
        elif str(arch) in ['s390']:
            return '-m31'
        elif str(the_os) == 'AIX':
            if str(arch) in ['ppc32']:
                return '-maix32'
            elif str(arch) in ['ppc64']:
                return '-maix64'
    elif str(compiler) == "intel":
        # https://software.intel.com/en-us/cpp-compiler-developer-guide-and-reference-m32-m64-qm32-qm64
        if str(arch) == "x86":
            return "/Qm32" if str(compiler_base) == "Visual Studio" else "-m32"
        elif str(arch) == "x86_64":
            return "/Qm64" if str(compiler_base) == "Visual Studio" else "-m64"
    return ""


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
    arch = conanfile.settings.get_safe("arch")

    compiler_base_version = conanfile.settings.get_safe("compiler.base.version")
    if hasattr(conanfile, 'settings_build'):
        os_build = conanfile.settings_build.get_safe('os')
    else:
        os_build = conanfile.settings.get_safe('os_build')
    if os_build is None:  # Assume is the same specified in host settings, not cross-building
        os_build = conanfile.settings.get_safe("os")

    if not compiler or not compiler_version or not arch:
        if os_build == "Windows":
            logger.warning("CMake generator could not be deduced from settings")
            return None
        return "Unix Makefiles"

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

    # The generator depends on the build machine, not the target
    if os_build == "Windows" and compiler != "qcc":
        return "MinGW Makefiles"  # it is valid only under Windows

    return "Unix Makefiles"
