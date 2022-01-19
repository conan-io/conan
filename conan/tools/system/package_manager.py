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
        self._mode = self._conanfile.conf[
                         "tools.system.package_manager:mode"] or MODE_CHECK  # install, check

    def packager_method(wrapped):
        def wrapper(self, *args, **kwargs):
            method_name = wrapped.__name__
            if self._active_tool == self.__class__.tool_name:
                if method_name in INSTALL_METHODS and self._mode == MODE_CHECK:
                    self._conanfile.output.warn("Can't {}. Please update packages manually or set "
                                                "'tools.system.package_manager:mode' to "
                                                "'install'".format(method_name))
                else:
                    wrapped(self, *args, **kwargs)
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

    @SystemPackageManagerTool.packager_method
    def install(self, packages, recommends=False):
        recommends_str = '' if recommends else '--no-install-recommends '
        command = "{}{} install -y {}{}".format(self.sudo_str, self.tool_name, recommends_str,
                                                " ".join(packages))
        return self._conanfile.run(command)

    @SystemPackageManagerTool.packager_method
    def update(self):
        command = "{}{} update".format(self.sudo_str, self.tool_name)
        return self._conanfile.run(command)

    def check(self, packages):
        not_installed = [pkg for pkg in packages if not self.check_package(pkg)]
        return not_installed

    @SystemPackageManagerTool.packager_method
    def check_package(self, package):
        command = "dpkg-query -W -f='${Status}' {} | grep -q \"ok installed\"".format(package)
        return self._conanfile.run(command)
