""" ConanFile user tools, as download, etc
"""
from __future__ import print_function
import sys
import os
from conans.errors import ConanException
from conans.util.files import _generic_algorithm_sum, load
from patch import fromfile, fromstring
from conans.client.rest.uploader_downloader import Downloader
import requests
from conans.client.output import ConanOutput
import platform
from conans.model.version import Version
from conans.util.log import logger
from conans.client.runner import ConanRunner
from contextlib import contextmanager
import multiprocessing


@contextmanager
def pythonpath(conanfile):
    old_path = sys.path[:]
    sys.path.extend(conanfile.deps_env_info.PYTHONPATH)
    yield
    sys.path = old_path


@contextmanager
def environment_append(env_vars):
    old_env = dict(os.environ)
    os.environ.update(env_vars)
    yield
    os.environ.clear()
    os.environ.update(old_env)


def build_sln_command(settings, sln_path, targets=None, upgrade_project=True):
    '''
    Use example:
        build_command = build_sln_command(self.settings, "myfile.sln", targets=["SDL2_image"])
        env = ConfigureEnvironment(self)
        command = "%s && %s" % (env.command_line_env, build_command)
        self.run(command)
    '''
    targets = targets or []
    command = "devenv %s /upgrade && " % sln_path if upgrade_project else ""
    command += "msbuild %s /p:Configuration=%s" % (sln_path, settings.build_type)
    if str(settings.arch) in ["x86_64", "x86"]:
        command += ' /p:Platform='
        command += '"x64"' if settings.arch == "x86_64" else '"x86"'
    elif "ARM" in str(settings.arch).upper():
        command += ' /p:Platform="ARM"'

    if targets:
        command += " /target:%s" % ";".join(targets)
    return command


def vcvars_command(settings):
    param = "x86" if settings.arch == "x86" else "amd64"
    existing_version = os.environ.get("VisualStudioVersion")
    if existing_version:
        command = ""
        existing_version = existing_version.split(".")[0]
        if existing_version != settings.compiler.version:
            raise ConanException("Error, Visual environment already set to %s\n"
                                 "Current settings visual version: %s"
                                 % (existing_version, settings.compiler.version))
    else:
        command = ('call "%%vs%s0comntools%%../../VC/vcvarsall.bat" %s'
                   % (settings.compiler.version, param))
    return command


def cpu_count():
    try:
        return multiprocessing.cpu_count()
    except NotImplementedError:
        print("WARN: multiprocessing.cpu_count() not implemented. Defaulting to 1 cpu")
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


def unzip(filename, destination="."):
    if (filename.endswith(".tar.gz") or filename.endswith(".tgz") or
        filename.endswith(".tbz2") or filename.endswith(".tar.bz2") or
            filename.endswith(".tar")):
        return untargz(filename, destination)
    import zipfile
    full_path = os.path.normpath(os.path.join(os.getcwd(), destination))

    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        def print_progress(extracted_size, uncompress_size):
            txt_msg = "Unzipping %.0f %%\r" % (extracted_size * 100.0 / uncompress_size)
            print(txt_msg, end='')
    else:
        def print_progress(extracted_size, uncompress_size):
            pass

    with zipfile.ZipFile(filename, "r") as z:
        uncompress_size = sum((file_.file_size for file_ in z.infolist()))
        print("Unzipping %s, this can take a while" % human_size(uncompress_size))
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
                    print("Error extract %s\n%s" % (file_.filename, str(e)))
        else:  # duplicated for, to avoid a platform check for each zipped file
            for file_ in z.infolist():
                extracted_size += file_.file_size
                print_progress(extracted_size, uncompress_size)
                try:
                    z.extract(file_, full_path)
                except Exception as e:
                    print("Error extract %s\n%s" % (file_.filename, str(e)))


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


def download(url, filename, verify=True):
    out = ConanOutput(sys.stdout, True)
    if verify:
        # We check the certificate using a list of known verifiers
        import conans.client.rest.cacert as cacert
        verify = cacert.file_path
    downloader = Downloader(requests, out, verify=verify)
    downloader.download(url, filename)
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


def patch(base_path=None, patch_file=None, patch_string=None, strip=0):
    """Applies a diff from file (patch_file)  or string (patch_string)
    in base_path directory or current dir if None"""

    if not patch_file and not patch_string:
        return
    if patch_file:
        patchset = fromfile(patch_file)
    else:
        patchset = fromstring(patch_string.encode())

    if not patchset.apply(root=base_path, strip=strip):
        raise ConanException("Failed to apply patch: %s" % patch_file)


# DETECT OS, VERSION AND DISTRIBUTIONS

class OSInfo(object):
    ''' Usage:
        print(os_info.is_linux) # True/False
        print(os_info.is_windows) # True/False
        print(os_info.is_macos) # True/False
        print(os_info.is_freebsd) # True/False

        print(os_info.linux_distro)  # debian, ubuntu, fedora, centos...

        print(os_info.os_version) # 5.1
        print(os_info.os_version_name) # Windows 7, El Capitan

        if os_info.os_version > "10.1":
            pass
        if os_info.os_version == "10.1.0":
            pass
    '''

    def __init__(self):
        self.os_version = None
        self.os_version_name = None
        self.is_linux = platform.system() == "Linux"
        self.linux_distro = None
        self.is_windows = platform.system() == "Windows"
        self.is_macos = platform.system() == "Darwin"
        self.is_freebsd = platform.system() == "FreeBSD"

        if self.is_linux:
            tmp = platform.linux_distribution(full_distribution_name=0)
            self.linux_distro = None
            self.linux_distro = tmp[0].lower()
            self.os_version = Version(tmp[1])
            self.os_version_name = tmp[2]
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

    @property
    def with_apt(self):
        return self.is_linux and self.linux_distro in ("debian", "ubuntu", "knoppix")

    @property
    def with_yum(self):
        return self.is_linux and self.linux_distro in ("centos", "redhat", "fedora")

    def get_win_os_version(self):
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
                        ('szCSDVersion', ctypes.c_wchar*128),
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

    def get_debian_version_name(self, version):
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

    def get_win_version_name(self, version):
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

    def get_osx_version_name(self, version):
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

    def get_freebsd_version(self):
        return platform.release().split("-")[0]

try:
    os_info = OSInfo()
except Exception as exc:
    logger.error(exc)
    print("Error detecting os_info")


class SystemPackageTool(object):

    def __init__(self, runner=None):
        self._runner = runner or ConanRunner()
        env_sudo = os.environ.get("CONAN_SYSREQUIRES_SUDO", None)
        self._sudo = (env_sudo != "False" and env_sudo != "0")
        self._os_info = OSInfo()

    def update(self):
        """
            Get the system package tool update command
        """
        sudo_str = "sudo " if self._sudo else ""
        update_command = None
        if self._os_info.with_apt:
            update_command = "%sapt-get update" % sudo_str
        elif self._os_info.with_yum:
            update_command = "%syum check-update" % sudo_str
        elif self._os_info.is_macos:
            update_command = "brew update"

        if update_command:
            print("Running: %s" % update_command)
            return self._runner(update_command, True)

    def install(self, package_name):
        '''
            Get the system package tool install command.
        '''
        sudo_str = "sudo " if self._sudo else ""
        install_command = None
        if self._os_info.with_apt:
            install_command = "%sapt-get install -y %s" % (sudo_str, package_name)
        elif self._os_info.with_yum:
            install_command = "%syum install -y %s" % (sudo_str, package_name)
        elif self._os_info.is_macos:
            install_command = "brew install %s" % package_name

        if install_command:
            print("Running: %s" % install_command)
            return self._runner(install_command, True)
        else:
            print("Warn: Only available for linux with apt-get or yum or OSx with brew")
            return None
