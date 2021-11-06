import math
import multiprocessing
import os
import platform
import subprocess
import sys
import warnings
from collections import namedtuple

from conans.client.tools.env import environment_append
from conans.client.tools.files import load, which
from conans.errors import CalledProcessErrorWithStderr, ConanException
from conans.model.version import Version
from conans.util.runners import check_output_runner


def args_to_string(args):
    if not args:
        return ""
    if sys.platform == 'win32':
        return subprocess.list2cmdline(args)
    else:
        return " ".join("'" + arg.replace("'", r"'\''") + "'" for arg in args)


class CpuProperties(object):

    def get_cpu_quota(self):
        return int(load("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"))

    def get_cpu_period(self):
        return int(load("/sys/fs/cgroup/cpu/cpu.cfs_period_us"))

    def get_cpus(self):
        try:
            cfs_quota_us = self.get_cpu_quota()
            cfs_period_us = self.get_cpu_period()
            if cfs_quota_us > 0 and cfs_period_us > 0:
                return int(math.ceil(cfs_quota_us / cfs_period_us))
        except:
            pass
        return multiprocessing.cpu_count()


def cpu_count(output=None):
    try:
        env_cpu_count = os.getenv("CONAN_CPU_COUNT", None)
        if env_cpu_count is not None and not env_cpu_count.isdigit():
            raise ConanException("Invalid CONAN_CPU_COUNT value '%s', "
                                 "please specify a positive integer" % env_cpu_count)
        if env_cpu_count:
            return int(env_cpu_count)
        else:
            return CpuProperties().get_cpus()
    except NotImplementedError:
        output.warning("multiprocessing.cpu_count() not implemented. Defaulting to 1 cpu")
    return 1  # Safe guess


# DETECT OS, VERSION AND DISTRIBUTIONS


class OSInfo(object):
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
        self.os_version_name = None
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

        if self.is_linux:
            self._get_linux_distro_info()
        elif self.is_windows:
            self.os_version = self.get_win_os_version()
            self.os_version_name = self.get_win_version_name(self.os_version)
        elif self.is_macos:
            self.os_version = Version(platform.mac_ver()[0])
            self.os_version_name = self.get_osx_version_name(self.os_version)
        elif self.is_freebsd:
            self.os_version = self.get_freebsd_version()
            self.os_version_name = "FreeBSD %s" % self.os_version
        elif self.is_solaris:
            self.os_version = Version(platform.release())
            self.os_version_name = self.get_solaris_version_name(self.os_version)
        elif self.is_aix:
            self.os_version = self.get_aix_version()
            self.os_version_name = "AIX %s" % self.os_version.minor(fill=False)

    def _get_linux_distro_info(self):
        import distro
        self.linux_distro = distro.id()
        self.os_version = Version(distro.version())
        version_name = distro.codename()
        self.os_version_name = version_name if version_name != "n/a" else ""
        if not self.os_version_name and self.linux_distro == "debian":
            self.os_version_name = self.get_debian_version_name(self.os_version)

    @property
    def with_apt(self):
        if not self.is_linux:
            return False

        # https://github.com/conan-io/conan/issues/8737 zypper-aptitude can fake it
        if "opensuse" in self.linux_distro or "sles" in self.linux_distro:
            return False

        apt_location = which('apt-get')
        if apt_location:
            # Check if we actually have the official apt package.
            try:
                output = check_output_runner([apt_location, 'moo'])
            except CalledProcessErrorWithStderr:
                return False
            else:
                # Yes, we have mooed today. :-) MOOOOOOOO.
                return True
        else:
            return False

    @property
    def with_yum(self):
        return self.is_linux and self.linux_distro in ("pidora", "fedora", "scientific", "centos",
                                                       "redhat", "rhel", "xenserver", "amazon",
                                                       "oracle", "amzn", "almalinux")

    @property
    def with_dnf(self):
        return self.is_linux and self.linux_distro == "fedora" and which('dnf')

    @property
    def with_pacman(self):
        if self.is_linux:
            return self.linux_distro in ["arch", "manjaro"]
        elif self.is_windows and which('uname.exe'):
            uname = check_output_runner(['uname.exe', '-s'])
            return uname.startswith('MSYS_NT') and which('pacman.exe')
        return False

    @property
    def with_zypper(self):
        if not self.is_linux:
            return False
        if "opensuse" in self.linux_distro or "sles" in self.linux_distro:
            return True
        return False

    @staticmethod
    def get_win_os_version():
        """
        Get's the OS major and minor versions.  Returns a tuple of
        (OS_MAJOR, OS_MINOR).
        """
        import ctypes

        class _OSVERSIONINFOEXW(ctypes.Structure):
            _fields_ = [('dwOSVersionInfoSize', ctypes.c_ulong),
                        ('dwMajorVersion', ctypes.c_ulong),
                        ('dwMinorVersion', ctypes.c_ulong),
                        ('dwBuildNumber', ctypes.c_ulong),
                        ('dwPlatformId', ctypes.c_ulong),
                        ('szCSDVersion', ctypes.c_wchar * 128),
                        ('wServicePackMajor', ctypes.c_ushort),
                        ('wServicePackMinor', ctypes.c_ushort),
                        ('wSuiteMask', ctypes.c_ushort),
                        ('wProductType', ctypes.c_byte),
                        ('wReserved', ctypes.c_byte)]

        os_version = _OSVERSIONINFOEXW()
        os_version.dwOSVersionInfoSize = ctypes.sizeof(os_version)
        if not hasattr(ctypes, "windll"):
            return None
        retcode = ctypes.windll.Ntdll.RtlGetVersion(ctypes.byref(os_version))
        if retcode != 0:
            return None

        return Version("%d.%d" % (os_version.dwMajorVersion, os_version.dwMinorVersion))

    @staticmethod
    def get_debian_version_name(version):
        if not version:
            return None
        elif version.major() == "8.Y.Z":
            return "jessie"
        elif version.major() == "7.Y.Z":
            return "wheezy"
        elif version.major() == "6.Y.Z":
            return "squeeze"
        elif version.major() == "5.Y.Z":
            return "lenny"
        elif version.major() == "4.Y.Z":
            return "etch"
        elif version.minor() == "3.1.Z":
            return "sarge"
        elif version.minor() == "3.0.Z":
            return "woody"

    @staticmethod
    def get_win_version_name(version):
        if not version:
            return None
        elif version.major() == "5.Y.Z":
            return "Windows XP"
        elif version.minor() == "6.0.Z":
            return "Windows Vista"
        elif version.minor() == "6.1.Z":
            return "Windows 7"
        elif version.minor() == "6.2.Z":
            return "Windows 8"
        elif version.minor() == "6.3.Z":
            return "Windows 8.1"
        elif version.minor() == "10.0.Z":
            return "Windows 10"

    @staticmethod
    def get_osx_version_name(version):
        if not version:
            return None
        elif version.minor() == "10.13.Z":
            return "High Sierra"
        elif version.minor() == "10.12.Z":
            return "Sierra"
        elif version.minor() == "10.11.Z":
            return "El Capitan"
        elif version.minor() == "10.10.Z":
            return "Yosemite"
        elif version.minor() == "10.9.Z":
            return "Mavericks"
        elif version.minor() == "10.8.Z":
            return "Mountain Lion"
        elif version.minor() == "10.7.Z":
            return "Lion"
        elif version.minor() == "10.6.Z":
            return "Snow Leopard"
        elif version.minor() == "10.5.Z":
            return "Leopard"
        elif version.minor() == "10.4.Z":
            return "Tiger"
        elif version.minor() == "10.3.Z":
            return "Panther"
        elif version.minor() == "10.2.Z":
            return "Jaguar"
        elif version.minor() == "10.1.Z":
            return "Puma"
        elif version.minor() == "10.0.Z":
            return "Cheetha"

    @staticmethod
    def get_freebsd_version():
        return platform.release().split("-")[0]

    @staticmethod
    def get_solaris_version_name(version):
        if not version:
            return None
        elif version.minor() == "5.10":
            return "Solaris 10"
        elif version.minor() == "5.11":
            return "Solaris 11"

    @staticmethod
    def get_aix_version():
        try:
            ret = check_output_runner("oslevel").strip()
            return Version(ret)
        except Exception:
            return Version("%s.%s" % (platform.version(), platform.release()))


def cross_building(conanfile, self_os=None, self_arch=None, skip_x64_x86=False):
    from conans.model.conan_file import ConanFile
    assert isinstance(conanfile, ConanFile)

    ret = get_cross_building_settings(conanfile, self_os, self_arch)
    build_os, build_arch, host_os, host_arch = ret

    if skip_x64_x86 and host_os is not None and (build_os == host_os) and \
            host_arch is not None and ((build_arch == "x86_64") and (host_arch == "x86") or
                                       (build_arch == "sparcv9") and (host_arch == "sparc") or
                                       (build_arch == "ppc64") and (host_arch == "ppc32")):
        return False

    if host_os is not None and (build_os != host_os):
        return True
    if host_arch is not None and (build_arch != host_arch):
        return True

    return False


def get_cross_building_settings(conanfile, self_os=None, self_arch=None):
    os_build, arch_build = get_build_os_arch(conanfile)
    os_host = conanfile.settings.get_safe("os")
    arch_host = conanfile.settings.get_safe("arch")

    return os_build, arch_build, os_host, arch_host


def get_gnu_triplet(os_, arch, compiler=None):
    """
    Returns string with <machine>-<vendor>-<op_system> triplet (<vendor> can be omitted in practice)

    :param os_: os to be used to create the triplet
    :param arch: arch to be used to create the triplet
    :param compiler: compiler used to create the triplet (only needed fo windows)
    """

    if os_ == "Windows" and compiler is None:
        raise ConanException("'compiler' parameter for 'get_gnu_triplet()' is not specified and "
                             "needed for os=Windows")

    # Calculate the arch
    machine = {"x86": "i686" if os_ != "Linux" else "x86",
               "x86_64": "x86_64",
               "armv8": "aarch64",
               "armv8_32": "aarch64",  # https://wiki.linaro.org/Platform/arm64-ilp32
               "armv8.3": "aarch64",
               "asm.js": "asmjs",
               "wasm": "wasm32",
               }.get(arch, None)

    if not machine:
        # https://wiki.debian.org/Multiarch/Tuples
        if os_ == "AIX":
            if "ppc32" in arch:
                machine = "rs6000"
            elif "ppc64" in arch:
                machine = "powerpc"
        elif "arm" in arch:
            machine = "arm"
        elif "ppc32be" in arch:
            machine = "powerpcbe"
        elif "ppc64le" in arch:
            machine = "powerpc64le"
        elif "ppc64" in arch:
            machine = "powerpc64"
        elif "ppc32" in arch:
            machine = "powerpc"
        elif "mips64" in arch:
            machine = "mips64"
        elif "mips" in arch:
            machine = "mips"
        elif "sparcv9" in arch:
            machine = "sparc64"
        elif "sparc" in arch:
            machine = "sparc"
        elif "s390x" in arch:
            machine = "s390x-ibm"
        elif "s390" in arch:
            machine = "s390-ibm"
        elif "sh4" in arch:
            machine = "sh4"
        elif "e2k" in arch:
            # https://lists.gnu.org/archive/html/config-patches/2015-03/msg00000.html
            machine = "e2k-unknown"

    if machine is None:
        raise ConanException("Unknown '%s' machine, Conan doesn't know how to "
                             "translate it to the GNU triplet, please report at "
                             " https://github.com/conan-io/conan/issues" % arch)

    # Calculate the OS
    if compiler == "gcc":
        windows_op = "w64-mingw32"
    elif compiler == "Visual Studio":
        windows_op = "windows-msvc"
    else:
        windows_op = "windows"

    op_system = {"Windows": windows_op,
                 "Linux": "linux-gnu",
                 "Darwin": "apple-darwin",
                 "Android": "linux-android",
                 "Macos": "apple-darwin",
                 "iOS": "apple-ios",
                 "watchOS": "apple-watchos",
                 "tvOS": "apple-tvos",
                 # NOTE: it technically must be "asmjs-unknown-emscripten" or
                 # "wasm32-unknown-emscripten", but it's not recognized by old config.sub versions
                 "Emscripten": "local-emscripten",
                 "AIX": "ibm-aix",
                 "Neutrino": "nto-qnx"}.get(os_, os_.lower())

    if os_ in ("Linux", "Android"):
        if "arm" in arch and "armv8" not in arch:
            op_system += "eabi"

        if (arch == "armv5hf" or arch == "armv7hf") and os_ == "Linux":
            op_system += "hf"

        if arch == "armv8_32" and os_ == "Linux":
            op_system += "_ilp32"  # https://wiki.linaro.org/Platform/arm64-ilp32

    return "%s-%s" % (machine, op_system)


def get_build_os_arch(conanfile):
    """ Returns the value for the 'os' and 'arch' settings for the build context """
    return conanfile.settings_build.get_safe('os'), conanfile.settings_build.get_safe('arch')
