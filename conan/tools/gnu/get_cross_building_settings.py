import os
import platform

from conans.errors import ConanException
from conans.model.version import Version
from conans.util.runners import check_output_runner


class _OSInfo(object):
    """ Usage:
        (os_info.is_linux) # True/False
        (os_info.is_windows) # True/False
        (os_info.is_macos) # True/False
        (os_info.is_freebsd) # True/False
        (os_info.is_solaris) # True/False

        (os_info.linux_distro)  # debian, ubuntu, fedora, centos...

        (os_info.os_version) # 5.1
        (os_info.os_version_name) # Windows 7, El Capitan

        if os_info.os_version > "10.1":
            pass
        if os_info.os_version == "10.1.0":
            pass
    """

    def __init__(self):
        system = platform.system()
        self.os_version = None

        self.is_linux = system == "Linux"
        self.linux_distro = None
        self.is_msys = system.startswith("MING") or system.startswith("MSYS_NT")
        self.is_cygwin = system.startswith("CYGWIN_NT")
        self.is_windows = system == "Windows" or self.is_msys or self.is_cygwin
        self.is_macos = system == "Darwin"
        self.is_freebsd = system == "FreeBSD"
        self.is_solaris = system == "SunOS"
        self.is_aix = system == "AIX"
        self.is_posix = os.pathsep == ':'

    def _get_linux_distro_info(self):
        import distro
        self.linux_distro = distro.id()
        self.os_version = Version(distro.version())

    @staticmethod
    def get_aix_architecture():
        processor = platform.processor()
        if "powerpc" in processor:
            kernel_bitness = _OSInfo().get_aix_conf("KERNEL_BITMODE")
            if kernel_bitness:
                return "ppc64" if kernel_bitness == "64" else "ppc32"
        elif "rs6000" in processor:
            return "ppc32"

    @staticmethod
    def get_aix_conf(options=None):
        options = " %s" % options if options else ""
        if not _OSInfo().is_aix:
            raise ConanException("Command only for AIX operating system")

        try:
            ret = check_output_runner("getconf%s" % options).strip()
            return ret
        except Exception:
            return None

    @staticmethod
    def get_solaris_architecture():
        # under intel solaris, platform.machine()=='i86pc' so we need to handle
        # it early to suport 64-bit
        processor = platform.processor()
        kernel_bitness, elf = platform.architecture()
        if "sparc" in processor:
            return "sparcv9" if kernel_bitness == "64bit" else "sparc"
        elif "i386" in processor:
            return "x86_64" if kernel_bitness == "64bit" else "x86"

    @staticmethod
    def get_e2k_architecture():
        return {
            "E1C+": "e2k-v4",  # Elbrus 1C+ and Elbrus 1CK
            "E2C+": "e2k-v2",  # Elbrus 2CM
            "E2C+DSP": "e2k-v2",  # Elbrus 2C+
            "E2C3": "e2k-v6",  # Elbrus 2C3
            "E2S": "e2k-v3",  # Elbrus 2S (aka Elbrus 4C)
            "E8C": "e2k-v4",  # Elbrus 8C and Elbrus 8C1
            "E8C2": "e2k-v5",  # Elbrus 8C2 (aka Elbrus 8CB)
            "E12C": "e2k-v6",  # Elbrus 12C
            "E16C": "e2k-v6",  # Elbrus 16C
            "E32C": "e2k-v7",  # Elbrus 32C
        }.get(platform.processor())


def _detected_os():
    if _OSInfo().is_macos:
        return "Macos"
    if _OSInfo().is_windows:
        return "Windows"
    return platform.system()


def _detected_architecture():
    # FIXME: Very weak check but not very common to run conan in other architectures
    machine = platform.machine()
    os_info = _OSInfo()
    arch = None

    if os_info.is_solaris:
        arch = _OSInfo.get_solaris_architecture()
    elif os_info.is_aix:
        arch = _OSInfo.get_aix_architecture()

    if arch:
        return arch

    if "ppc64le" in machine:
        return "ppc64le"
    elif "ppc64" in machine:
        return "ppc64"
    elif "ppc" in machine:
        return "ppc32"
    elif "mips64" in machine:
        return "mips64"
    elif "mips" in machine:
        return "mips"
    elif "sparc64" in machine:
        return "sparcv9"
    elif "sparc" in machine:
        return "sparc"
    elif "aarch64" in machine:
        return "armv8"
    elif "arm64" in machine:
        return "armv8"
    elif "64" in machine:
        return "x86_64"
    elif "86" in machine:
        return "x86"
    elif "armv8" in machine:
        return "armv8"
    elif "armv7" in machine:
        return "armv7"
    elif "arm" in machine:
        return "armv6"
    elif "s390x" in machine:
        return "s390x"
    elif "s390" in machine:
        return "s390"
    elif "sun4v" in machine:
        return "sparc"
    elif "e2k" in machine:
        return _OSInfo.get_e2k_architecture()


def _get_build_os_arch(conanfile):
    """ Returns the value for the 'os' and 'arch' settings for the build context """
    if hasattr(conanfile, 'settings_build'):
        return conanfile.settings_build.get_safe('os'), conanfile.settings_build.get_safe('arch')
    else:
        return conanfile.settings.get_safe('os_build'), conanfile.settings.get_safe('arch_build')


def _get_cross_building_settings(conanfile, self_os=None, self_arch=None):
    os_build, arch_build = _get_build_os_arch(conanfile)
    if not hasattr(conanfile, 'settings_build'):
        # Let it override from outside only if no 'profile_build' is used
        os_build = self_os or os_build or _detected_os()
        arch_build = self_arch or arch_build or _detected_architecture()

    os_host = conanfile.settings.get_safe("os")
    arch_host = conanfile.settings.get_safe("arch")

    return os_build, arch_build, os_host, arch_host
