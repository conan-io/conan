from conans.errors import ConanException


class SystemPackageManagerTool(object):
    install_methods = ["install", "update"]
    mode_check = "check"
    tool_name = None
    install_command = ""
    update_command = ""
    check_command = ""

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._active_tool = self._conanfile.conf["tools.system.package_manager:tool"]
        self._sudo = self._conanfile.conf["tools.system.package_manager:sudo"]
        self._sudo_askpass = self._conanfile.conf["tools.system.package_manager:sudo_askpass"]
        self._mode = self._conanfile.conf["tools.system.package_manager:mode"] or self.mode_check
        self._arch = self._conanfile.settings.get_safe("arch")
        self._arch_names = {}
        self._arch_separator = ""

    def get_package_name(self, package):
        # TODO: should we only add the arch if cross-building?
        if self._arch in self._arch_names:
            return "{}{}{}".format(package, self._arch_separator,
                                   self._arch_names.get(self._arch))
        return package

    @property
    def sudo_str(self):
        sudo = "sudo " if self._sudo else ""
        askpass = "-A " if self._sudo and self._sudo_askpass else ""
        return "{}{}".format(sudo, askpass)

    def method_decorator(wrapped):
        def wrapper(self, *args, **kwargs):
            method_name = wrapped.__name__
            if self._active_tool == self.__class__.tool_name:
                if method_name in self.install_methods and self._mode == self.mode_check:
                    raise ConanException("Can't {}. Please update packages manually or set "
                                         "'tools.system.package_manager:mode' to "
                                         "'install'".format(method_name))
                else:
                    return wrapped(self, *args, **kwargs)
        return wrapper

    @method_decorator  # noqa
    def install(self, packages, update=False, check=False, **kwargs):
        if update:
            self.update()
        if check:
            packages = self.check(packages)
        packages_arch = [self.get_package_name(package) for package in packages]
        if packages_arch:
            command = self.install_command.format(sudo=self.sudo_str,
                                                  tool=self.tool_name,
                                                  packages=" ".join(packages_arch),
                                                  **kwargs)
            return self._conanfile.run(command)

    @method_decorator  # noqa
    def update(self):
        command = self.update_command.format(sudo=self.sudo_str,
                                             tool=self.tool_name)
        return self._conanfile.run(command)

    @method_decorator  # noqa
    def check(self, packages):
        missing = [pkg for pkg in packages if self.check_package(self.get_package_name(pkg)) != 0]
        return missing

    def check_package(self, package):
        command = self.check_command.format(tool=self.tool_name,
                                            package=package)
        return self._conanfile.run(command, ignore_errors=True)


class Apt(SystemPackageManagerTool):
    # TODO: apt? apt-get?
    tool_name = "apt-get"
    install_command = "{sudo}{tool} install -y {recommends}{packages}"
    update_command = "{sudo}{tool} update"
    check_command = "dpkg-query -W -f='${{Status}}' {package} | grep -q \"ok installed\""

    def __init__(self, conanfile, arch_names=None):
        super(Apt, self).__init__(conanfile)
        self._arch_names = {"x86_64": "amd64",
                            "x86": "i386",
                            "ppc32": "powerpc",
                            "ppc64le": "ppc64el",
                            "armv7": "arm",
                            "armv7hf": "armhf",
                            "armv8": "arm64",
                            "s390x": "s390x"} if arch_names is None else arch_names

        self._arch_separator = ":"

    @SystemPackageManagerTool.method_decorator
    def install(self, packages, update=False, check=False, recommends=False):
        recommends_str = '' if recommends else '--no-install-recommends '
        return super(Apt, self).install(packages, update=update, check=check,
                                        recommends=recommends_str)


class Yum(SystemPackageManagerTool):
    tool_name = "yum"
    install_command = "{sudo}{tool} install -y {packages}"
    update_command = "{sudo}{tool} check-update -y"
    check_command = "rpm -q {package}"

    def __init__(self, conanfile, arch_names=None):
        super(Yum, self).__init__(conanfile)
        self._arch_names = {"x86_64": "x86_64",
                            "x86": "i?86",
                            "ppc32": "powerpc",
                            "ppc64le": "ppc64le",
                            "armv7": "armv7",
                            "armv7hf": "armv7hl",
                            "armv8": "aarch64",
                            "s390x": "s390x"} if arch_names is None else arch_names
        self._arch_separator = "."


class Dnf(Yum):
    tool_name = "dnf"


class Brew(SystemPackageManagerTool):
    tool_name = "brew"
    install_command = "{sudo}{tool} install {packages}"
    update_command = "{sudo}{tool} update"
    check_command = 'test -n "$({tool} ls --versions {package})"'


class Pkg(SystemPackageManagerTool):
    tool_name = "pkg"
    install_command = "{sudo}{tool} install -y {packages}"
    update_command = "{sudo}{tool} update"
    check_command = "{tool} info {package}"


class PkgUtil(SystemPackageManagerTool):
    tool_name = "pkgutil"
    install_command = "{sudo}{tool} --install --yes {packages}"
    update_command = "{sudo}{tool} --catalog"
    check_command = 'test -n "`{tool} --list {package}`"'


class Chocolatey(SystemPackageManagerTool):
    tool_name = "choco"
    install_command = "{tool} --install --yes {packages}"
    update_command = "{tool} outdated"
    check_command = '{tool} search --local-only --exact {package} | ' \
                    'findstr /c:"1 packages installed."'


class PacMan(SystemPackageManagerTool):
    tool_name = "pacman"
    install_command = "{sudo}{tool} -S --noconfirm {packages}"
    update_command = "{sudo}{tool} -Syyu --noconfirm"
    check_command = "{tool} -Qi {package}"

    def __init__(self, conanfile, arch_names=None):
        super(PacMan, self).__init__(conanfile)
        self._arch_names = {"x86": "lib32"} if arch_names is None else arch_names
        self._arch_separator = "-"


class Zypper(SystemPackageManagerTool):
    tool_name = "zypper"
    install_command = "{sudo}{tool} --non-interactive in {packages}"
    update_command = "{sudo}{tool} --non-interactive ref"
    check_command = "rpm -q {package}"
