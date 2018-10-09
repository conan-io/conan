import multiprocessing
import platform
import subprocess
import sys

import os

from conans.client.tools.env import environment_append
from conans.errors import ConanException
from conans.model.version import Version
from conans.util.log import logger
from conans.client.tools import which

_global_output = None


def args_to_string(args):
    if not args:
        return ""
    if sys.platform == 'win32':
        return subprocess.list2cmdline(args)
    else:
        return " ".join("'" + arg.replace("'", r"'\''") + "'" for arg in args)


def cpu_count():
    try:
        env_cpu_count = os.getenv("CONAN_CPU_COUNT", None)
        return int(env_cpu_count) if env_cpu_count else multiprocessing.cpu_count()
    except NotImplementedError:
        _global_output.warn("multiprocessing.cpu_count() not implemented. Defaulting to 1 cpu")
    return 1  # Safe guess


def detected_architecture():
    # FIXME: Very weak check but not very common to run conan in other architectures
    machine = platform.machine()
    if "ppc64le" in machine:
        return "ppc64le"
    elif "ppc64" in machine:
        return "ppc64"
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

    return None

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
        self.os_version = None
        self.os_version_name = None
        self.is_linux = platform.system() == "Linux"
        self.linux_distro = None
        self.is_windows = platform.system() == "Windows"
        self.is_macos = platform.system() == "Darwin"
        self.is_freebsd = platform.system() == "FreeBSD"
        self.is_solaris = platform.system() == "SunOS"
        self.is_posix = os.pathsep == ':'

        if self.is_linux:
            import distro
            self.linux_distro = distro.id()
            self.os_version = Version(distro.version())
            version_name = distro.codename()
            self.os_version_name = version_name if version_name != "n/a" else ""
            if not self.os_version_name and self.linux_distro == "debian":
                self.os_version_name = self.get_debian_version_name(self.os_version)
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

    @property
    def with_apt(self):
        return self.is_linux and self.linux_distro in \
                                 ("debian", "ubuntu", "knoppix", "linuxmint", "raspbian")

    @property
    def with_yum(self):
        return self.is_linux and self.linux_distro in \
                                 ("centos", "redhat", "fedora", "pidora", "scientific",
                                  "xenserver", "amazon", "oracle", "rhel")

    @property
    def with_pacman(self):
        if self.is_linux:
            return self.linux_distro in ["arch", "manjaro"]
        elif self.is_windows and which('uname.exe'):
            uname = subprocess.check_output(['uname.exe', '-s']).decode()
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
    def bash_path():
        if os.getenv("CONAN_BASH_PATH"):
            return os.getenv("CONAN_BASH_PATH")
        return which("bash")

    @staticmethod
    def uname(options=None):
        options = " %s" % options if options else ""
        if platform.system() != "Windows":
            raise ConanException("Command only for Windows operating system")
        custom_bash_path = OSInfo.bash_path()
        if not custom_bash_path:
            raise ConanException("bash is not in the path")

        command = '"%s" -c "uname%s"' % (custom_bash_path, options)
        try:
            # the uname executable is many times located in the same folder as bash.exe
            with environment_append({"PATH": [os.path.dirname(custom_bash_path)]}):
                ret = subprocess.check_output(command, shell=True, ).decode().strip().lower()
                return ret
        except Exception:
            return None

    @staticmethod
    def detect_windows_subsystem():
        from conans.client.tools.win import CYGWIN, MSYS2, MSYS, WSL
        try:
            output = OSInfo.uname()
        except ConanException:
            return None
        if not output:
            return None
        if "cygwin" in output:
            return CYGWIN
        elif "msys" in output or "mingw" in output:
            output = OSInfo.uname("-or")
            if output.startswith("2"):
                return MSYS2
            elif output.startswith("1"):
                return MSYS
            else:
                return None
        elif "linux" in output:
            return WSL
        else:
            return None


def cross_building(settings, self_os=None, self_arch=None):

    ret = get_cross_building_settings(settings, self_os, self_arch)
    build_os, build_arch, host_os, host_arch = ret

    if host_os is not None and (build_os != host_os):
        return True
    if host_arch is not None and (build_arch != host_arch):
        return True

    return False


def get_cross_building_settings(settings, self_os=None, self_arch=None):
    build_os = self_os or settings.get_safe("os_build") or \
               {"Darwin": "Macos"}.get(platform.system(), platform.system())
    build_arch = self_arch or settings.get_safe("arch_build") or detected_architecture()
    host_os = settings.get_safe("os")
    host_arch = settings.get_safe("arch")

    return build_os, build_arch, host_os, host_arch


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
               "armv8": "aarch64"}.get(arch, None)

    if not machine:
        # https://wiki.debian.org/Multiarch/Tuples
        if "arm" in arch:
            machine = "arm"
        elif "ppc64le" in arch:
            machine = "powerpc64le"
        elif "ppc64" in arch:
            machine = "powerpc64"
        elif "powerpc" in arch:
            machine = "powerpc"
        elif "mips64" in arch:
            machine = "mips64"
        elif "mips" in arch:
            machine = "mips"
        elif "sparcv9" in arch:
            machine = "sparc64"
        elif "sparc" in arch:
            machine = "sparc"

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
                 "iOS": "apple-darwin",
                 "watchOS": "apple-darwin",
                 "tvOS": "apple-darwin"}.get(os_, os_.lower())

    if os_ in ("Linux", "Android"):
        if "arm" in arch and arch != "armv8":
            op_system += "eabi"

        if arch == "armv7hf" and os_ == "Linux":
            op_system += "hf"

    return "%s-%s" % (machine, op_system)


try:
    os_info = OSInfo()
except Exception as exc:
    logger.error(exc)
    _global_output.error("Error detecting os_info")
