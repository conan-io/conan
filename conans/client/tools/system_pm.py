import os
import sys
import six

from conans.client.runner import ConanRunner
from conans.client.tools.oss import OSInfo, cross_building, get_cross_building_settings
from conans.client.tools.files import which
from conans.errors import ConanException, ConanInvalidSystemRequirements
from conans.util.env_reader import get_env
from conans.util.fallbacks import default_output


class SystemPackageTool(object):

    def __init__(self, runner=None, os_info=None, tool=None, recommends=False, output=None,
                 conanfile=None, default_mode="enabled"):
        output = output if output else conanfile.output if conanfile else None
        self._output = default_output(output, 'conans.client.tools.system_pm.SystemPackageTool')
        os_info = os_info or OSInfo()
        self._is_up_to_date = False
        self._tool = tool or self._create_tool(os_info, output=self._output)
        self._tool._sudo_str = self._get_sudo_str()
        self._tool._runner = runner or ConanRunner(output=self._output)
        self._tool._recommends = recommends
        self._conanfile = conanfile
        self._default_mode = default_mode

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
    def _create_tool(os_info, output):
        if os_info.with_apt:
            return AptTool(output=output)
        elif os_info.with_dnf:
            return DnfTool(output=output)
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

    def _get_sysrequire_mode(self):
        allowed_modes = ("enabled", "verify", "disabled")
        mode = get_env("CONAN_SYSREQUIRES_MODE", self._default_mode)
        mode_lower = mode.lower()
        if mode_lower not in allowed_modes:
            raise ConanException("CONAN_SYSREQUIRES_MODE=%s is not allowed, allowed modes=%r"
                                 % (mode, allowed_modes))
        return mode_lower

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

    def install(self, packages, update=True, force=False, arch_names=None):
        """ Get the system package tool install command and install one package

        :param packages: String with a package to be installed or a list with its variants e.g. "libusb-dev libxusb-devel"
        :param update: Run update command before to install
        :param force: Force installing all packages
        :param arch_names: Package suffix/prefix name used by installer tool e.g. {"x86_64": "amd64"}
        :return: None
        """
        packages = [packages] if isinstance(packages, str) else list(packages)
        packages = self._get_package_names(packages, arch_names)

        mode = self._get_sysrequire_mode()

        if mode in ("verify", "disabled"):
            # Report to output packages need to be installed
            if mode == "disabled":
                self._output.info("The following packages need to be installed:\n %s"
                                  % "\n".join(packages))
                return

            if mode == "verify" and not self._installed(packages):
                self._output.error("The following packages need to be installed:\n %s"
                                   % "\n".join(packages))
                raise ConanInvalidSystemRequirements("Aborted due to CONAN_SYSREQUIRES_MODE=%s. "
                                     "Some system packages need to be installed" % mode)
            return

        if not force and self._installed(packages):
            return

        # From here system packages can be updated/modified
        if update and not self._is_up_to_date:
            self.update()
        self._install_any(packages)

    def install_packages(self, packages, update=True, force=False, arch_names=None):
        """ Get the system package tool install command and install all packages and/or variants.
            Inputs:
            "pkg-variant1"  # (1) Install only one package
            ["pkg-variant1", "otherpkg", "thirdpkg"] # (2) All must be installed
            [("pkg-variant1", "pkg-variant2"), "otherpkg", "thirdpkg"] # (3) Install only one variant
                                                                             and all other packages
            "pkg1 pkg2", "pkg3 pkg4" # (4) Invalid
            ["pkg1 pkg2", "pkg3 pkg4"] # (5) Invalid

        :param packages: Supports multiple formats (string,list,tuple). Lists and tuples into a list
        are considered variants and is processed just like self.install(). A list of string is
        considered a list of packages to be installed (only not installed yet).
        :param update: Run update command before to install
        :param force: Force installing all packages, including all installed.
        :param arch_names: Package suffix/prefix name used by installer tool e.g. {"x86_64": "amd64"}
        :return: None
        """
        packages = [packages] if isinstance(packages, six.string_types) else list(packages)
        # only one (first) variant will be installed
        list_variants = list(filter(lambda x: isinstance(x, (tuple, list)), packages))
        # all packages will be installed
        packages = list(filter(lambda x: not isinstance(x, (tuple, list)), packages))

        if [pkg for pkg in packages if " " in pkg]:
            raise ConanException("Each string must contain only one package to be installed. "
                                 "Use a list instead e.g. ['foo', 'bar'].")

        for variant in list_variants:
            self.install(variant, update=update, force=force, arch_names=arch_names)

        packages = self._get_package_names(packages, arch_names)

        mode = self._get_sysrequire_mode()

        if mode in ("verify", "disabled"):
            # Report to output packages need to be installed
            if mode == "disabled":
                self._output.info("The following packages need to be installed:\n %s"
                                  % "\n".join(packages))
                return

            if mode == "verify" and self._to_be_installed(packages):
                self._output.error("The following packages need to be installed:\n %s"
                                   % "\n".join(packages))
                raise ConanInvalidSystemRequirements("Aborted due to CONAN_SYSREQUIRES_MODE=%s. "
                                     "Some system packages need to be installed" % mode)
            return

        packages = packages if force else self._to_be_installed(packages)
        if not force and not packages:
            return

        # From here system packages can be updated/modified
        if update and not self._is_up_to_date:
            self.update()
        self._install_all(packages)

    def _get_package_names(self, packages, arch_names):
        """ Parse package names according it architecture

        :param packages: list with all package to be installed e.g. ["libusb-dev libfoobar-dev"]
        :param arch_names: Package suffix/prefix name used by installer tool
        :return: list with all parsed names e.g. ["libusb-dev:armhf libfoobar-dev:armhf"]
        """
        if self._conanfile and self._conanfile.settings and cross_building(self._conanfile):
            _, build_arch, _, host_arch = get_cross_building_settings(self._conanfile)
            arch = host_arch or build_arch
            parsed_packages = []
            for package in packages:
                if isinstance(package, (tuple, list)):
                    parsed_packages.append(tuple(self._get_package_names(package, arch_names)))
                else:
                    for package_name in package.split(" "):
                        parsed_packages.append(self._tool.get_package_name(package_name, arch,
                                                                           arch_names))
            return parsed_packages
        return packages

    def installed(self, package_name):
        return self._tool.installed(package_name)

    def _to_be_installed(self, packages):
        """ Returns a list with all not installed packages.
        """
        not_installed = [pkg for pkg in packages if not self._tool.installed(pkg)]
        return not_installed

    def _installed(self, packages):
        """ Return True if at least one of the packages is installed.
        """
        if not packages:
            return True

        for pkg in packages:
            if self._tool.installed(pkg):
                self._output.info("Package already installed: %s" % pkg)
                return True
        return False

    def _install_all(self, packages):
        self._tool.install(" ".join(sorted(packages)))

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

    def get_package_name(self, package, arch, arch_names):
        """ Retrieve package name to installed according the target arch.

        :param package: Regular package name e.g libusb-dev
        :param arch: Host arch from Conanfile.settings
        :param arch_names: Dictionary with suffix/prefix names e.g {"x86_64": "amd64"}
        :return: Package name for Tool e.g. libusb-dev:i386
        """
        return package


class NullTool(BaseTool):
    def add_repository(self, repository, repo_key=None):
        pass

    def update(self):
        pass

    def install(self, package_name):
        self._output.warn("Only available for linux with apt-get, yum, or pacman or OSX with brew or"
                          " FreeBSD with pkg or Solaris with pkgutil")

    def installed(self, package_name):
        return False


class AptTool(BaseTool):
    def add_repository(self, repository, repo_key=None):
        if repo_key:
            _run(self._runner, "wget -qO - %s | %sapt-key add -" % (repo_key, self._sudo_str),
                 output=self._output)
        _run(self._runner, "%sapt-add-repository %s" % (self._sudo_str, repository),
             output=self._output)

    def update(self):
        _run(self._runner, "%sapt-get update" % self._sudo_str, output=self._output)

    def install(self, package_name):
        recommends_str = '' if self._recommends else '--no-install-recommends '
        _run(self._runner,
             "%sapt-get install -y %s%s" % (self._sudo_str, recommends_str, package_name),
             output=self._output)

    def installed(self, package_name):
        exit_code = self._runner("dpkg-query -W -f='${Status}' %s | grep -q \"ok installed\""
                                 % package_name, None)
        return exit_code == 0

    def get_package_name(self, package, arch, arch_names):
        if arch_names is None:
            arch_names = {"x86_64": "amd64",
                         "x86": "i386",
                         "ppc32": "powerpc",
                         "ppc64le": "ppc64el",
                         "armv7": "arm",
                         "armv7hf": "armhf",
                         "armv8": "arm64",
                         "s390x": "s390x"}
        if arch in arch_names:
            return "%s:%s" % (package, arch_names[arch])
        return package


class YumTool(BaseTool):
    def add_repository(self, repository, repo_key=None):
        raise ConanException("YumTool::add_repository not implemented")

    def update(self):
        _run(self._runner, "%syum check-update -y" % self._sudo_str, accepted_returns=[0, 100],
             output=self._output)

    def install(self, package_name):
        _run(self._runner, "%syum install -y %s" % (self._sudo_str, package_name),
             output=self._output)

    def installed(self, package_name):
        exit_code = self._runner("rpm -q %s" % package_name, None)
        return exit_code == 0

    def get_package_name(self, package, arch, arch_names):
        if arch_names is None:
            arch_names = {"x86_64": "x86_64",
                         "x86": "i?86",
                         "ppc32": "powerpc",
                         "ppc64le": "ppc64le",
                         "armv7": "armv7",
                         "armv7hf": "armv7hl",
                         "armv8": "aarch64",
                         "s390x": "s390x"}
        if arch in arch_names:
            return "%s.%s" % (package, arch_names[arch])
        return package


class DnfTool(YumTool):
    def add_repository(self, repository, repo_key=None):
        raise ConanException("DnfTool::add_repository not implemented")

    def update(self):
        _run(self._runner, "%sdnf check-update -y" % self._sudo_str, accepted_returns=[0, 100],
             output=self._output)

    def install(self, package_name):
        _run(self._runner, "%sdnf install -y %s" % (self._sudo_str, package_name),
             output=self._output)


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

    def get_package_name(self, package, arch, arch_names):
        if arch_names is None:
            arch_names = {"x86": "lib32"}
        if arch in arch_names:
            return "%s-%s" % (arch_names[arch], package)
        return package


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

    def get_package_name(self, package, arch, arch_names):
        if arch_names is None:
            arch_names = {"x86": "i586"}
        if arch in arch_names:
            return "%s.%s" % (arch_names[arch], package)
        return package


def _run(runner, command, output, accepted_returns=None):
    accepted_returns = accepted_returns or [0, ]
    output.info("Running: %s" % command)
    if runner(command, True) not in accepted_returns:
        raise ConanException("Command '%s' failed" % command)
