import math
import multiprocessing
import os
import platform
import subprocess
import sys

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
            self.os_version_name = "AIX %s.%s" % (self.os_version.major, self.os_version.minor)

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
        elif version.major == 8:
            return "jessie"
        elif version.major == 7:
            return "wheezy"
        elif version.major == 6:
            return "squeeze"
        elif version.major == 5:
            return "lenny"
        elif version.major == 4:
            return "etch"
        elif (version.major, version.minor) == (3, 1):
            return "sarge"
        elif (version.major, version.minor) == (3, 0):
            return "woody"

    @staticmethod
    def get_win_version_name(version):
        if not version:
            return None
        elif version.major == 5:
            return "Windows XP"
        elif version.major == 6 and version.minor == 0:
            return "Windows Vista"
        elif version.major == 6 and version.minor == 1:
            return "Windows 7"
        elif version.major == 6 and version.minor == 2:
            return "Windows 8"
        elif version.major == 6 and version.minor == 3:
            return "Windows 8.1"
        elif version.major == 10:
            return "Windows 10"
        elif version.major == 11:
            return "Windows 11"

    @staticmethod
    def get_osx_version_name(version):
        if not version:
            return None
        elif version.minor == 13:
            return "High Sierra"
        elif version.minor == 12:
            return "Sierra"
        elif version.minor == 11:
            return "El Capitan"
        elif version.minor == 10:
            return "Yosemite"
        elif version.minor == 9:
            return "Mavericks"
        elif version.minor == 8:
            return "Mountain Lion"
        elif version.minor == 7:
            return "Lion"
        elif version.minor == 6:
            return "Snow Leopard"
        elif version.minor == 5:
            return "Leopard"
        elif version.minor == 4:
            return "Tiger"
        elif version.minor == 3:
            return "Panther"
        elif version.minor == 2:
            return "Jaguar"
        elif version.minor == 1:
            return "Puma"
        elif version.minor == 0:
            return "Cheetha"

    @staticmethod
    def get_freebsd_version():
        return platform.release().split("-")[0]

    @staticmethod
    def get_solaris_version_name(version):
        if not version:
            return None
        elif version.major == "5" and version.minor == "10":
            return "Solaris 10"
        elif version.major == "5" and version.minor == "11":
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


def get_build_os_arch(conanfile):
    """ Returns the value for the 'os' and 'arch' settings for the build context """
    return conanfile.settings_build.get_safe('os'), conanfile.settings_build.get_safe('arch')
