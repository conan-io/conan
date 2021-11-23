import subprocess

from conan.tools.env import Environment
from conans.errors import ConanException
from conans.util.runners import check_output_runner


class PkgConfig:

    def __init__(self, conanfile, package, pkg_config_path=None):
        """
        :param package: library (package) name, such as libastral
        """
        self._conanfile = conanfile
        self._package = package
        self._info = {}
        self._pkg_config_path = pkg_config_path
        self._variables = {}

    def _parse_output(self, option):
        executable = self._conanfile.conf["tools.gnu:pkg_config"] or "pkg-config"
        command = [executable, '--' + option, self._package, '--print-errors']
        try:
            env = Environment()
            if self._pkg_config_path:
                env.prepend_path("PKG_CONFIG_PATH", self._pkg_config_path)
            with env.vars(self._conanfile).apply():
                return check_output_runner(command).strip()
        except subprocess.CalledProcessError as e:
            raise ConanException('pkg-config command %s failed with error: %s' % (command, e))

    def _get_option(self, option):
        if option not in self._info:
            self._info[option] = self._parse_output(option)
        return self._info[option]

    @property
    def includedirs(self):
        return [include[2:] for include in self._get_option('cflags-only-I').split()]

    @property
    def cflags(self):
        return [flag for flag in self._get_option('cflags-only-other').split()
                if not flag.startswith("-D")]

    @property
    def defines(self):
        return [flag for flag in self._get_option('cflags-only-other').split()
                if flag.startswith("-D")]

    @property
    def libdirs(self):
        return [lib[2:] for lib in self._get_option('libs-only-L').split()]

    @property
    def libs(self):
        return [lib[2:] for lib in self._get_option('libs-only-l').split()]

    @property
    def linkflags(self):
        return self._get_option('libs-only-other').split()

    @property
    def provides(self):
        return self._get_option('print-provides')

    @property
    def version(self):
        return self._get_option('modversion')

    @property
    def variables(self):
        if self._variables is None:
            variable_names = self._parse_output('print-variables').split()
            self._variables = {}
            for name in variable_names:
                self._variables[name] = self._parse_output('variable=%s' % name)
        return self._variables

    def cpp_info(self, cpp_info, is_system=True):
        if not self.provides:
            raise ConanException("PkgConfig error, '{}' files not available".format(self._package))
        if is_system:
            cpp_info.system_libs = self.libs
        else:
            cpp_info.libs = self.libs
        cpp_info.libdirs = self.libdirs
        cpp_info.sharedlinkflags = self.linkflags
        cpp_info.exelinkflags = self.linkflags
        cpp_info.defines = self.defines
        cpp_info.includedirs = self.includedirs
        cpp_info.cflags = self.cflags
        cpp_info.cxxflags = self.cflags
