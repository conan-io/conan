from conans.errors import ConanException

CHECK_METHODS = ["check"]
MODIFY_METHODS = ["install", "update"]


class Tool(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._active_tool = self._conanfile.conf["tools.system.package_manager:tool"]
        self._sudo = self._conanfile.conf["tools.system.package_manager:sudo"]
        self._sudo_askpass = self._conanfile.conf["tools.system.package_manager:sudo_askpass"]
        self._mode = self._conanfile.conf["tools.system.package_manager:mode"] or "check" # install, check

    def packager_method(wrapped):
        def wrapper(self, *args, **kwargs):
            # function to make all checks
            wrapped(self, *args, **kwargs)
        return wrapper

    # def __getattribute__(self, name):
    #     if name not in CHECK_METHODS + MODIFY_METHODS:
    #         return object.__getattribute__(self, name)
    #     if self._active_tool == self.__class__.name:
    #         try:
    #             if name in MODIFY_METHODS and self._mode != "install":
    #                 self._conanfile.output.warn(
    #                     "Can't {}. Please update packages manually or set "
    #                     "'tools.system.package_manager:mode' to 'install'".format(name))
    #             else:
    #                 return object.__getattribute__(self, name)
    #         except AttributeError:
    #             raise ConanException("There is no {} method defined in tool: {}".format(name,
    #                                                                                     self.__class__.name))

    @property
    def sudo_str(self):
        sudo = "sudo " if self._sudo else ""
        askpass = "-A " if self._sudo and self._sudo_askpass else ""
        return "{}{}".format(sudo, askpass)


class Apt(Tool):
    # TODO: apt? apt-get?
    name = "apt-get"

    @Tool.packager_method
    def install(self, packages, recommends=False):
        recommends_str = '' if recommends else '--no-install-recommends '
        command = "{}{} install -y {}{}".format(self.sudo_str, self.name, recommends_str,
                                                " ".join(packages))
        return self._conanfile.run(command)

    @Tool.packager_method
    def update(self):
        command = "{}{} update".format(self.sudo_str, self.name)
        return self._conanfile.run(command)

    def check(self, packages):
        not_installed = [pkg for pkg in packages if not self.check_package(pkg)]
        return not_installed

    @Tool.packager_method
    def check_package(self, package):
        command = "dpkg-query -W -f='${Status}' {} | grep -q \"ok installed\"".format(package)
        return self._conanfile.run(command)
