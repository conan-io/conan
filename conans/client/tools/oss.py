import os
import platform

from conans.client.tools.files import which
from conans.errors import CalledProcessErrorWithStderr
from conans.util.runners import check_output_runner


class OSInfo(object):
   # Leaving this as temp helper for SystemPackageTool

    def __init__(self):
        system = platform.system()
        self.os_version = None
        self.os_version_name = None
        self.is_linux = system == "Linux"
        self.linux_distro = None
        self.is_windows = system == "Windows" or self.is_msys or self.is_cygwin
        self.is_macos = system == "Darwin"
        if self.is_linux:
            import distro
            self.linux_distro = distro.id()

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
