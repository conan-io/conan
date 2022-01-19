CHECK_METHODS = ["check"]
INSTALL_METHODS = ["install", "update"]

MODE_CHECK = "check"
MODE_INSTALL = "install"


class SystemPackageManagerTool(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._active_tool = self._conanfile.conf["tools.system.package_manager:tool"]
        self._sudo = self._conanfile.conf["tools.system.package_manager:sudo"]
        self._sudo_askpass = self._conanfile.conf["tools.system.package_manager:sudo_askpass"]
        self._mode = self._conanfile.conf["tools.system.package_manager:mode"] or MODE_CHECK
        self._arch_names = None
        self._arch = self._conanfile.settings.get_safe("arch")
        self._arch_separator = ""

    def get_package_name(self, package):
        # TODO: should we only add the arch if cross-building?
        if self._arch in self._arch_names:
            return "{}{}{}".format(package, self._arch_separator,
                                   self._arch_names.get(self._arch, ""))

    def decorator(wrapped):
        def wrapper(self, *args, **kwargs):
            method_name = wrapped.__name__
            if self._active_tool == self.__class__.tool_name:
                if method_name in INSTALL_METHODS and self._mode == MODE_CHECK:
                    self._conanfile.output.warn("Can't {}. Please update packages manually or set "
                                                "'tools.system.package_manager:mode' to "
                                                "'install'".format(method_name))
                else:
                    return wrapped(self, *args, **kwargs)
            else:
                self._conanfile.output.warn("Ignoring call to {}.{}. Set "
                                            "'tools.system.package_manager:tool' to activate tool "
                                            "as the system package manager "
                                            "tool".format(self.__class__.__name__, method_name))

        return wrapper

    @property
    def sudo_str(self):
        sudo = "sudo " if self._sudo else ""
        askpass = "-A " if self._sudo and self._sudo_askpass else ""
        return "{}{}".format(sudo, askpass)


class Apt(SystemPackageManagerTool):
    # TODO: apt? apt-get?
    tool_name = "apt-get"

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

    @SystemPackageManagerTool.decorator
    def install(self, packages, recommends=False, update=False):
        if update:
            self.update()
        recommends_str = '' if recommends else '--no-install-recommends '
        packages_arch = [self.get_package_name(package) for package in packages]
        command = "{}{} install -y {}{}".format(self.sudo_str, self.tool_name, recommends_str,
                                                " ".join(packages_arch))
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def update(self):
        command = "{}{} update".format(self.sudo_str, self.tool_name)
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def check(self, packages):
        not_installed = [pkg for pkg in packages if self.check_package(self.get_package_name(pkg)) != 0]
        return not_installed

    def check_package(self, package):
        command = "dpkg-query -W -f='${{Status}}' {} | grep -q \"ok installed\"".format(package)
        return self._conanfile.run(command, ignore_errors=True)


class Yum(SystemPackageManagerTool):
    tool_name = "yum"

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

    @SystemPackageManagerTool.decorator
    def install(self, packages):
        packages_arch = [self.get_package_name(package) for package in packages]
        command = "{}{} install -y {}".format(self.sudo_str, self.tool_name, " ".join(packages_arch))
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def update(self):
        command = "{}{} check-update -y".format(self.sudo_str, self.tool_name)
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def check(self, packages):
        not_installed = [self.get_package_name(pkg) for pkg in packages if
                         self.check_package(self.get_package_name(pkg)) != 0]
        return not_installed

    def check_package(self, package):
        command = "rpm -q {}".format(package)
        return self._conanfile.run(command, ignore_errors=True)


class Dnf(Yum):
    tool_name = "dnf"


class Brew(SystemPackageManagerTool):
    tool_name = "brew"

    @SystemPackageManagerTool.decorator
    def install(self, packages):
        command = "{}{} install {}".format(self.sudo_str, self.tool_name, " ".join(packages))
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def update(self):
        command = "{}{} update".format(self.sudo_str, self.tool_name)
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def check(self, packages):
        not_installed = [pkg for pkg in packages if self.check_package(pkg) != 0]
        return not_installed

    def check_package(self, package):
        command = 'test -n "$({} ls --versions {})"'.format(self.tool_name, package)
        return self._conanfile.run(command, ignore_errors=True)


class Pkg(SystemPackageManagerTool):
    tool_name = "pkg"

    @SystemPackageManagerTool.decorator
    def install(self, packages):
        command = "{}{} install -y {}".format(self.sudo_str, self.tool_name, " ".join(packages))
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def update(self):
        command = "{}{} update".format(self.sudo_str, self.tool_name)
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def check(self, packages):
        not_installed = [pkg for pkg in packages if self.check_package(pkg) != 0]
        return not_installed

    def check_package(self, package):
        command = "{} info {}".format(self.tool_name, package)
        return self._conanfile.run(command, ignore_errors=True)


class PkgUtil(SystemPackageManagerTool):
    tool_name = "pkgutil"

    @SystemPackageManagerTool.decorator
    def install(self, packages):
        command = "{}{} --install --yes {}".format(self.sudo_str, self.tool_name, " ".join(packages))
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def update(self):
        command = "{}{} --catalog".format(self.sudo_str, self.tool_name)
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def check(self, packages):
        not_installed = [pkg for pkg in packages if self.check_package(pkg) != 0]
        return not_installed

    def check_package(self, package):
        command = 'test -n "`{} --list {}`"'.format(self.tool_name, package)
        return self._conanfile.run(command, ignore_errors=True)


class Chocolatey(SystemPackageManagerTool):
    tool_name = "choco"

    @SystemPackageManagerTool.decorator
    def install(self, packages):
        command = "{} --install --yes {}".format(self.tool_name, " ".join(packages))
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def update(self):
        command = "{} outdated".format(self.tool_name)
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def check(self, packages):
        not_installed = [pkg for pkg in packages if self.check_package(pkg) != 0]
        return not_installed

    def check_package(self, package):
        command = '{} search --local-only --exact {} | ' \
                  'findstr /c:"1 packages installed."'.format(self.tool_name, package)
        return self._conanfile.run(command, ignore_errors=True)


class PacMan(SystemPackageManagerTool):
    tool_name = "pacman"

    def __init__(self, conanfile, arch_names=None):
        super(PacMan, self).__init__(conanfile)
        self._arch_names = {"x86": "lib32"} if arch_names is None else arch_names
        self._arch_separator = "-"

    @SystemPackageManagerTool.decorator
    def install(self, packages):
        packages_arch = [self.get_package_name(pkg) for pkg in packages]
        command = "{}{} -S --noconfirm {}".format(self.sudo_str, self.tool_name,
                                                  " ".join(packages_arch))
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def update(self):
        command = "{}{} -Syyu --noconfirm".format(self.sudo_str, self.tool_name)
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def check(self, packages):
        not_installed = [self.get_package_name(pkg) for pkg in packages if
                         self.check_package(self.get_package_name(pkg)) != 0]
        return not_installed

    def check_package(self, package):
        command = "{} -Qi {}".format(self.tool_name, package)
        return self._conanfile.run(command, ignore_errors=True)


class Zypper(SystemPackageManagerTool):
    tool_name = "zypper"

    def __init__(self, conanfile, arch_names=None):
        super(Zypper, self).__init__(conanfile)
        self._arch_names = {"x86": "i586"} if arch_names is None else arch_names
        self._arch_separator = "."

    @SystemPackageManagerTool.decorator
    def install(self, packages):
        packages_arch = [self.get_package_name(pkg) for pkg in packages]
        command = "{}{}  --non-interactive in {}".format(self.sudo_str, self.tool_name,
                                                         " ".join(packages_arch))
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def update(self):
        command = "{}{} --non-interactive ref".format(self.sudo_str, self.tool_name)
        return self._conanfile.run(command)

    @SystemPackageManagerTool.decorator
    def check(self, packages):
        not_installed = [self.get_package_name(pkg) for pkg in packages if
                         self.check_package(self.get_package_name(pkg)) != 0]
        return not_installed

    def check_package(self, package):
        command = "{} -Qi {}".format(self.tool_name, package)
        return self._conanfile.run(command, ignore_errors=True)
