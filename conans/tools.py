""" ConanFile user tools, as download, etc
"""
from __future__ import print_function

import logging
import multiprocessing
import os
import platform
import re
import subprocess
import sys


from contextlib import contextmanager

import requests
from patch import fromfile, fromstring

from conans.client.output import ConanOutput
from conans.client.rest.uploader_downloader import Downloader
from conans.client.runner import ConanRunner
from conans.errors import ConanException
from conans.model.version import Version
# noinspection PyUnresolvedReferences
from conans.util.files import _generic_algorithm_sum, load, save, sha256sum, sha1sum, md5sum, md5
from conans.util.log import logger

# Default values
_global_requester = requests
_global_output = ConanOutput(sys.stdout)


def unix_path(path):
    """"Used to translate windows paths to MSYS unix paths like
    c/users/path/to/file"""
    pattern = re.compile(r'([a-z]):\\', re.IGNORECASE)
    return pattern.sub('/\\1/', path).replace('\\', '/').lower()


def escape_windows_cmd(command):
    """ To use in a regular windows cmd.exe
        1. Adds escapes so the argument can be unpacked by CommandLineToArgvW()
        2. Adds escapes for cmd.exe so the argument survives cmd.exe's substitutions.

        Useful to escape commands to be executed in a windows bash (msys2, cygwin etc)
    """
    quoted_arg = subprocess.list2cmdline([command])
    return "".join(["^%s" % arg if arg in r'()%!^"<>&|' else arg for arg in quoted_arg])


def run_in_windows_bash(conanfile, bashcmd, cwd=None):
    """ Will run a unix command inside the msys2 environment
        It requires to have MSYS2 in the path and MinGW
    """
    if platform.system() != "Windows":
        raise ConanException("Command only for Windows operating system")
    # This needs to be set so that msys2 bash profile will set up the environment correctly.
    try:
        arch = conanfile.settings.arch  # Maybe arch doesn't exist
    except:
        arch = None
    env_vars = {"MSYSTEM": "MINGW32" if arch == "x86" else "MINGW64",
                "MSYS2_PATH_TYPE": "inherit"}
    with environment_append(env_vars):
        curdir = unix_path(cwd or os.path.abspath(os.path.curdir))
        # Needed to change to that dir inside the bash shell
        to_run = 'cd "%s" && %s ' % (curdir, bashcmd)
        custom_bash_path = os.getenv("CONAN_BASH_PATH", "bash")
        wincmd = '%s --login -c %s' % (custom_bash_path, escape_windows_cmd(to_run))
        conanfile.output.info('run_in_windows_bash: %s' % wincmd)
        conanfile.run(wincmd)


def args_to_string(args):
    if not args:
        return ""
    if sys.platform == 'win32':
        return subprocess.list2cmdline(args)
    else:
        return " ".join("'" + arg.replace("'", r"'\''") + "'" for arg in args)


@contextmanager
def chdir(newdir):
    old_path = os.getcwd()
    os.chdir(newdir)
    try:
        yield
    finally:
        os.chdir(old_path)


@contextmanager
def pythonpath(conanfile):
    old_path = sys.path[:]
    python_path = conanfile.env.get("PYTHONPATH", None)
    if python_path:
        if isinstance(python_path, list):
            sys.path.extend(python_path)
        else:
            sys.path.append(python_path)

    yield
    sys.path = old_path


@contextmanager
def environment_append(env_vars):
    """
    :param env_vars: List of simple environment vars. {name: value, name2: value2} => e.j: MYVAR=1
                     The values can also be lists of appendable environment vars. {name: [value, value2]}
                      => e.j. PATH=/path/1:/path/2
    :return: None
    """
    old_env = dict(os.environ)
    for name, value in env_vars.items():
        if isinstance(value, list):
            env_vars[name] = os.pathsep.join(value)
            if name in old_env:
                env_vars[name] += os.pathsep + old_env[name]
    os.environ.update(env_vars)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def msvc_build_command(settings, sln_path, targets=None, upgrade_project=True, build_type=None,
                       arch=None):
    """ Do both: set the environment variables and call the .sln build
    """
    vcvars = vcvars_command(settings)
    build = build_sln_command(settings, sln_path, targets, upgrade_project, build_type, arch)
    command = "%s && %s" % (vcvars, build)
    return command


def build_sln_command(settings, sln_path, targets=None, upgrade_project=True, build_type=None,
                      arch=None):
    """
    Use example:
        build_command = build_sln_command(self.settings, "myfile.sln", targets=["SDL2_image"])
        command = "%s && %s" % (tools.vcvars_command(self.settings), build_command)
        self.run(command)
    """
    targets = targets or []
    command = "devenv %s /upgrade && " % sln_path if upgrade_project else ""
    build_type = build_type or settings.build_type
    arch = arch or settings.arch
    if not build_type:
        raise ConanException("Cannot build_sln_command, build_type not defined")
    if not arch:
        raise ConanException("Cannot build_sln_command, arch not defined")
    command += "msbuild %s /p:Configuration=%s" % (sln_path, build_type)
    arch = str(arch)
    if arch in ["x86_64", "x86"]:
        command += ' /p:Platform='
        command += '"x64"' if arch == "x86_64" else '"x86"'
    elif "ARM" in arch.upper():
        command += ' /p:Platform="ARM"'

    if targets:
        command += " /target:%s" % ";".join(targets)
    return command


def vcvars_command(settings):
    arch_setting = settings.get_safe("arch")
    compiler_version = settings.get_safe("compiler.version")
    if not compiler_version:
        raise ConanException("compiler.version setting required for vcvars not defined")

    param = "x86" if arch_setting == "x86" else "amd64"
    existing_version = os.environ.get("VisualStudioVersion")
    if existing_version:
        command = "echo Conan:vcvars already set"
        existing_version = existing_version.split(".")[0]
        if existing_version != compiler_version:
            raise ConanException("Error, Visual environment already set to %s\n"
                                 "Current settings visual version: %s"
                                 % (existing_version, compiler_version))
    else:
        env_var = "vs%s0comntools" % compiler_version
        try:
            vs_path = os.environ[env_var]
        except KeyError:
            raise ConanException("VS '%s' variable not defined. Please install VS or define "
                                 "the variable (VS2017)" % env_var)
        if env_var != "vs150comntools":
            command = ('call "%s../../VC/vcvarsall.bat" %s' % (vs_path, param))
        else:
            command = ('call "%s../../VC/Auxiliary/Build/vcvarsall.bat" %s' % (vs_path, param))
    return command


def cpu_count():
    try:
        env_cpu_count = os.getenv("CONAN_CPU_COUNT", None)
        return int(env_cpu_count) if env_cpu_count else multiprocessing.cpu_count()
    except NotImplementedError:
        _global_output.warn("multiprocessing.cpu_count() not implemented. Defaulting to 1 cpu")
    return 1  # Safe guess


def human_size(size_bytes):
    """
    format a size in bytes into a 'human' file size, e.g. bytes, KB, MB, GB, TB, PB
    Note that bytes/KB will be reported in whole numbers but MB and above will have
    greater precision.  e.g. 1 byte, 43 bytes, 443 KB, 4.3 MB, 4.43 GB, etc
    """
    if size_bytes == 1:
        return "1 byte"

    suffixes_table = [('bytes', 0), ('KB', 0), ('MB', 1), ('GB', 2), ('TB', 2), ('PB', 2)]

    num = float(size_bytes)
    for suffix, precision in suffixes_table:
        if num < 1024.0:
            break
        num /= 1024.0

    if precision == 0:
        formatted_size = "%d" % num
    else:
        formatted_size = str(round(num, ndigits=precision))

    return "%s %s" % (formatted_size, suffix)


def unzip(filename, destination=".", keep_permissions=False):
    """
    Unzip a zipped file
    :param filename: Path to the zip file
    :param destination: Destination folder
    :param keep_permissions: Keep the zip permissions. WARNING: Can be dangerous if the zip was not created in a NIX
    system, the bits could produce undefined permission schema. Use only this option if you are sure that the
    zip was created correctly.
    :return:
    """
    if (filename.endswith(".tar.gz") or filename.endswith(".tgz") or
            filename.endswith(".tbz2") or filename.endswith(".tar.bz2") or
            filename.endswith(".tar")):
        return untargz(filename, destination)
    import zipfile
    full_path = os.path.normpath(os.path.join(os.getcwd(), destination))

    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        def print_progress(extracted_size, uncompress_size):
            txt_msg = "Unzipping %.0f %%" % (extracted_size * 100.0 / uncompress_size)
            _global_output.rewrite_line(txt_msg)
    else:
        def print_progress(extracted_size, uncompress_size):
            pass

    with zipfile.ZipFile(filename, "r") as z:
        uncompress_size = sum((file_.file_size for file_ in z.infolist()))
        _global_output.info("Unzipping %s, this can take a while" % human_size(uncompress_size))
        extracted_size = 0
        if platform.system() == "Windows":
            for file_ in z.infolist():
                extracted_size += file_.file_size
                print_progress(extracted_size, uncompress_size)
                try:
                    # Win path limit is 260 chars
                    if len(file_.filename) + len(full_path) >= 260:
                        raise ValueError("Filename too long")
                    z.extract(file_, full_path)
                except Exception as e:
                    _global_output.error("Error extract %s\n%s" % (file_.filename, str(e)))
        else:  # duplicated for, to avoid a platform check for each zipped file
            for file_ in z.infolist():
                extracted_size += file_.file_size
                print_progress(extracted_size, uncompress_size)
                try:
                    z.extract(file_, full_path)
                    if keep_permissions:
                        # Could be dangerous if the ZIP has been created in a non nix system
                        # https://bugs.python.org/issue15795
                        perm = file_.external_attr >> 16 & 0xFFF
                        os.chmod(os.path.join(full_path, file_.filename), perm)
                except Exception as e:
                    _global_output.error("Error extract %s\n%s" % (file_.filename, str(e)))


def untargz(filename, destination="."):
    import tarfile
    with tarfile.TarFile.open(filename, 'r:*') as tarredgzippedFile:
        tarredgzippedFile.extractall(destination)


def get(url):
    """ high level downloader + unziper + delete temporary zip
    """
    filename = os.path.basename(url)
    download(url, filename)
    unzip(filename)
    os.unlink(filename)


def ftp_download(ip, filename, login='', password=''):
    import ftplib
    try:
        ftp = ftplib.FTP(ip, login, password)
        ftp.login()
        filepath, filename = os.path.split(filename)
        if filepath:
            ftp.cwd(filepath)
        with open(filename, 'wb') as f:
            ftp.retrbinary('RETR ' + filename, f.write)
    except Exception as e:
        raise ConanException("Error in FTP download from %s\n%s" % (ip, str(e)))
    finally:
        try:
            ftp.quit()
        except:
            pass


def download(url, filename, verify=True, out=None, retry=2, retry_wait=5):
    out = out or ConanOutput(sys.stdout, True)
    if verify:
        # We check the certificate using a list of known verifiers
        import conans.client.rest.cacert as cacert
        verify = cacert.file_path
    downloader = Downloader(_global_requester, out, verify=verify)
    downloader.download(url, filename, retry=retry, retry_wait=retry_wait)
    out.writeln("")


#     save(filename, content)


def replace_in_file(file_path, search, replace):
    content = load(file_path)
    content = content.replace(search, replace)
    content = content.encode("utf-8")
    with open(file_path, "wb") as handle:
        handle.write(content)


def check_with_algorithm_sum(algorithm_name, file_path, signature):
    real_signature = _generic_algorithm_sum(file_path, algorithm_name)
    if real_signature != signature:
        raise ConanException("%s signature failed for '%s' file."
                             " Computed signature: %s" % (algorithm_name,
                                                          os.path.basename(file_path),
                                                          real_signature))


def check_sha1(file_path, signature):
    check_with_algorithm_sum("sha1", file_path, signature)


def check_md5(file_path, signature):
    check_with_algorithm_sum("md5", file_path, signature)


def check_sha256(file_path, signature):
    check_with_algorithm_sum("sha256", file_path, signature)


def patch(base_path=None, patch_file=None, patch_string=None, strip=0, output=None):
    """Applies a diff from file (patch_file)  or string (patch_string)
    in base_path directory or current dir if None"""

    class PatchLogHandler(logging.Handler):
        def __init__(self):
            logging.Handler.__init__(self, logging.DEBUG)
            self.output = output or ConanOutput(sys.stdout, True)
            self.patchname = patch_file if patch_file else "patch"

        def emit(self, record):
            logstr = self.format(record)
            if record.levelno == logging.WARN:
                self.output.warn("%s: %s" % (self.patchname, logstr))
            else:
                self.output.info("%s: %s" % (self.patchname, logstr))

    patchlog = logging.getLogger("patch")
    if patchlog:
        patchlog.handlers = []
        patchlog.addHandler(PatchLogHandler())

    if not patch_file and not patch_string:
        return
    if patch_file:
        patchset = fromfile(patch_file)
    else:
        patchset = fromstring(patch_string.encode())

    if not patchset:
        raise ConanException("Failed to parse patch: %s" % (patch_file if patch_file else "string"))

    if not patchset.apply(root=base_path, strip=strip):
        raise ConanException("Failed to apply patch: %s" % patch_file)


def cross_building(settings, self_os=None, self_arch=None):
    self_os = self_os or platform.system()
    self_arch = self_arch or detected_architecture()
    os_setting = settings.get_safe("os")
    arch_setting = settings.get_safe("arch")
    platform_os = {"Darwin": "Macos"}.get(self_os, self_os)
    if self_os == os_setting and self_arch == "x86_64" and arch_setting == "x86":
        return False  # not really considered cross

    if os_setting and platform_os != os_setting:
        return True
    if arch_setting and self_arch != arch_setting:
        return True

    return False


def detected_architecture():
    # FIXME: Very weak check but not very common to run conan in other architectures
    if "64" in platform.machine():
        return "x86_64"
    elif "86" in platform.machine():
        return "x86"
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
                                  "xenserver", "amazon", "oracle")

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


try:
    os_info = OSInfo()
except Exception as exc:
    logger.error(exc)
    _global_output.error("Error detecting os_info")


class SystemPackageTool(object):

    def __init__(self, runner=None, os_info=None, tool=None):
        env_sudo = os.environ.get("CONAN_SYSREQUIRES_SUDO", None)
        self._sudo = (env_sudo != "False" and env_sudo != "0")
        os_info = os_info or OSInfo()
        self._is_up_to_date = False
        self._tool = tool or self._create_tool(os_info)
        self._tool._sudo_str = "sudo " if self._sudo else ""
        self._tool._runner = runner or ConanRunner()

    def _create_tool(self, os_info):
        if os_info.with_apt:
            return AptTool()
        elif os_info.with_yum:
            return YumTool()
        elif os_info.is_macos:
            return BrewTool()
        else:
            return NullTool()

    def update(self):
        """
            Get the system package tool update command
        """
        self._is_up_to_date = True
        self._tool.update()

    def install(self, packages, update=True, force=False):
        '''
            Get the system package tool install command.
        '''
        packages = [packages] if isinstance(packages, str) else list(packages)
        if not force and self._installed(packages):
            return
        if update and not self._is_up_to_date:
            self.update()
        self._install_any(packages)

    def _installed(self, packages):
        for pkg in packages:
            if self._tool.installed(pkg):
                _global_output.info("Package already installed: %s" % pkg)
                return True
        return False

    def _install_any(self, packages):
        if len(packages) == 1:
            return self._tool.install(packages[0])
        for pkg in packages:
            try:
                return self._tool.install(pkg)
            except ConanException:
                pass
        raise ConanException("Could not install any of %s" % packages)


class NullTool(object):
    def update(self):
        pass

    def install(self, package_name):
        _global_output.warn("Only available for linux with apt-get or yum or OSx with brew")

    def installed(self, package_name):
        return False


class AptTool(object):
    def update(self):
        _run(self._runner, "%sapt-get update" % self._sudo_str)

    def install(self, package_name):
        _run(self._runner, "%sapt-get install -y %s" % (self._sudo_str, package_name))

    def installed(self, package_name):
        exit_code = self._runner("dpkg -s %s" % package_name, None)
        return exit_code == 0


class YumTool(object):
    def update(self):
        _run(self._runner, "%syum check-update" % self._sudo_str)

    def install(self, package_name):
        _run(self._runner, "%syum install -y %s" % (self._sudo_str, package_name))

    def installed(self, package_name):
        exit_code = self._runner("rpm -q %s" % package_name, None)
        return exit_code == 0


class BrewTool(object):
    def update(self):
        _run(self._runner, "brew update")

    def install(self, package_name):
        _run(self._runner, "brew install %s" % package_name)

    def installed(self, package_name):
        exit_code = self._runner('test -n "$(brew ls --versions %s)"' % package_name, None)
        return exit_code == 0


def _run(runner, command):
    _global_output.info("Running: %s" % command)
    if runner(command, True) != 0:
        raise ConanException("Command '%s' failed" % command)
