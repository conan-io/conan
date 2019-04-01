import os
import sys

from conans.client.runner import ConanRunner
from conans.client.tools.oss import OSInfo
from conans.client.tools.files import which
from conans.errors import ConanException
from conans.util.env_reader import get_env
from conans.util.fallbacks import default_output


class SystemPackageTool(object):

    def __init__(self, runner=None, os_info=None, tool=None, recommends=False, output=None):

        self._output = default_output(output, 'conans.client.tools.system_pm.SystemPackageTool')
        os_info = os_info or OSInfo()
        self._is_up_to_date = False
        self._tool = tool or self._create_tool(os_info, output=self._output)
        self._tool._sudo_str = self._get_sudo_str()
        self._tool._runner = runner or ConanRunner()
        self._tool._recommends = recommends

    @staticmethod
    def _get_sudo_str():
        if not SystemPackageTool._is_sudo_enabled():
            return ""

        if hasattr(sys.stdout, "isatty") and not sys.stdout.isatty():
            return "sudo -A "
        else:
            return "sudo "

    @staticmethod
    def _is_sudo_enabled():
        if "CONAN_SYSREQUIRES_SUDO" not in os.environ:
            if not which("sudo"):
                return False
            if os.name == 'posix' and os.geteuid() == 0:
                return False
            if os.name == 'nt':
                return False
        return get_env("CONAN_SYSREQUIRES_SUDO", True)

    @staticmethod
    def _get_sysrequire_mode():
        allowed_modes = ("enabled", "verify", "disabled")
        mode = get_env("CONAN_SYSREQUIRES_MODE", "enabled")
        mode_lower = mode.lower()
        if mode_lower not in allowed_modes:
            raise ConanException("CONAN_SYSREQUIRES_MODE=%s is not allowed, allowed modes=%r" % (mode, allowed_modes))
        return mode_lower

    @staticmethod
    def _create_tool(os_info, output):
        if os_info.with_apt:
            return AptTool(output=output)
        elif os_info.with_yum:
            return YumTool(output=output)
        elif os_info.with_pacman:
            return PacManTool(output=output)
        elif os_info.is_macos:
            return BrewTool(output=output)
        elif os_info.is_freebsd:
            return PkgTool(output=output)
        elif os_info.is_solaris:
            return PkgUtilTool(output=output)
        elif os_info.with_zypper:
            return ZypperTool(output=output)
        else:
            return NullTool(output=output)

    def add_repository(self, repository, repo_key=None, update=True):
        self._tool.add_repository(repository, repo_key=repo_key)
        if update:
            self.update()

    def update(self):
        """
            Get the system package tool update command
        """
        mode = self._get_sysrequire_mode()
        if mode in ("disabled", "verify"):
            self._output.info("Not updating system_requirements. CONAN_SYSREQUIRES_MODE=%s" % mode)
            return
        self._is_up_to_date = True
        self._tool.update()

    def install(self, packages, update=True, force=False):
        """
            Get the system package tool install command.
        '"""
        packages = [packages] if isinstance(packages, str) else list(packages)

        mode = self._get_sysrequire_mode()

        if mode in ("verify", "disabled"):
            # Report to output packages need to be installed
            if mode == "disabled":
                self._output.info("The following packages need to be installed:\n %s" % "\n".join(packages))
                return

            if mode == "verify" and not self._installed(packages):
                self._output.error("The following packages need to be installed:\n %s" % "\n".join(packages))
                raise ConanException(
                    "Aborted due to CONAN_SYSREQUIRES_MODE=%s. Some system packages need to be installed" % mode
                )

        if not force and self._installed(packages):
            return

        # From here system packages can be updated/modified
        if update and not self._is_up_to_date:
            self.update()
        self._install_any(packages)

    def _installed(self, packages):
        if not packages:
            return True

        for pkg in packages:
            if self._tool.installed(pkg):
                self._output.info("Package already installed: %s" % pkg)
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


class BaseTool(object):
    def __init__(self, output=None):
        self._output = default_output(output, 'conans.client.tools.system_pm.BaseTool')


class NullTool(BaseTool):
    def add_repository(self, repository, repo_key=None):
        pass

    def update(self):
        pass

    def install(self, package_name):
        self._output.warn("Only available for linux with apt-get, yum, or pacman or OSX with brew or "
                            "FreeBSD with pkg or Solaris with pkgutil")

    def installed(self, package_name):
        return False


class AptTool(BaseTool):
    def add_repository(self, repository, repo_key=None):
        _run(self._runner, "%sapt-add-repository %s" % (self._sudo_str, repository),
             output=self._output)
        if repo_key:
            _run(self._runner, "wget -qO - %s | %sapt-key add -" % (repo_key, self._sudo_str),
                 output=self._output)

    def update(self):
        _run(self._runner, "%sapt-get update" % self._sudo_str, output=self._output)

    def install(self, package_name):
        recommends_str = '' if self._recommends else '--no-install-recommends '
        _run(self._runner, "%sapt-get install -y %s%s" % (self._sudo_str, recommends_str, package_name),
             output=self._output)

    def installed(self, package_name):
        exit_code = self._runner("dpkg-query -W -f='${Status}' %s | grep -q \"ok installed\"" % package_name, None)
        return exit_code == 0


class YumTool(BaseTool):
    def add_repository(self, repository, repo_key=None):
        raise ConanException("YumTool::add_repository not implemented")

    def update(self):
        _run(self._runner, "%syum update -y" % self._sudo_str, accepted_returns=[0, 100],
             output=self._output)

    def install(self, package_name):
        _run(self._runner, "%syum install -y %s" % (self._sudo_str, package_name),
             output=self._output)

    def installed(self, package_name):
        exit_code = self._runner("rpm -q %s" % package_name, None)
        return exit_code == 0


class BrewTool(BaseTool):
    def add_repository(self, repository, repo_key=None):
        raise ConanException("BrewTool::add_repository not implemented")

    def update(self):
        _run(self._runner, "brew update", output=self._output)

    def install(self, package_name):
        _run(self._runner, "brew install %s" % package_name, output=self._output)

    def installed(self, package_name):
        exit_code = self._runner('test -n "$(brew ls --versions %s)"' % package_name, None)
        return exit_code == 0


class PkgTool(BaseTool):
    def add_repository(self, repository, repo_key=None):
        raise ConanException("PkgTool::add_repository not implemented")

    def update(self):
        _run(self._runner, "%spkg update" % self._sudo_str, output=self._output)

    def install(self, package_name):
        _run(self._runner, "%spkg install -y %s" % (self._sudo_str, package_name),
             output=self._output)

    def installed(self, package_name):
        exit_code = self._runner("pkg info %s" % package_name, None)
        return exit_code == 0


class PkgUtilTool(BaseTool):
    def add_repository(self, repository, repo_key=None):
        raise ConanException("PkgUtilTool::add_repository not implemented")

    def update(self):
        _run(self._runner, "%spkgutil --catalog" % self._sudo_str, output=self._output)

    def install(self, package_name):
        _run(self._runner, "%spkgutil --install --yes %s" % (self._sudo_str, package_name),
             output=self._output)

    def installed(self, package_name):
        exit_code = self._runner('test -n "`pkgutil --list %s`"' % package_name, None)
        return exit_code == 0


class ChocolateyTool(BaseTool):
    def add_repository(self, repository, repo_key=None):
        raise ConanException("ChocolateyTool::add_repository not implemented")

    def update(self):
        _run(self._runner, "choco outdated", output=self._output)

    def install(self, package_name):
        _run(self._runner, "choco install --yes %s" % package_name, output=self._output)

    def installed(self, package_name):
        exit_code = self._runner('choco search --local-only --exact %s | '
                                 'findstr /c:"1 packages installed."' % package_name, None)
        return exit_code == 0


class PacManTool(BaseTool):
    def add_repository(self, repository, repo_key=None):
        raise ConanException("PacManTool::add_repository not implemented")

    def update(self):
        _run(self._runner, "%spacman -Syyu --noconfirm" % self._sudo_str, output=self._output)

    def install(self, package_name):
        _run(self._runner, "%spacman -S --noconfirm %s" % (self._sudo_str, package_name),
             output=self._output)

    def installed(self, package_name):
        exit_code = self._runner("pacman -Qi %s" % package_name, None)
        return exit_code == 0


class ZypperTool(BaseTool):
    def add_repository(self, repository, repo_key=None):
        raise ConanException("ZypperTool::add_repository not implemented")

    def update(self):
        _run(self._runner, "%szypper --non-interactive ref" % self._sudo_str, output=self._output)

    def install(self, package_name):
        _run(self._runner, "%szypper --non-interactive in %s" % (self._sudo_str, package_name),
             output=self._output)

    def installed(self, package_name):
        exit_code = self._runner("rpm -q %s" % package_name, None)
        return exit_code == 0


def _run(runner, command, output, accepted_returns=None):
    accepted_returns = accepted_returns or [0, ]
    output.info("Running: %s" % command)
    if runner(command, True) not in accepted_returns:
        raise ConanException("Command '%s' failed" % command)
