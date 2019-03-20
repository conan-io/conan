import os
from contextlib import contextmanager

from conans.client import tools
from conans.client.output import Color, ScopedOutput
from conans.client.tools.env import environment_append, no_op, pythonpath
from conans.client.tools.oss import OSInfo
from conans.errors import ConanException
from conans.model.build_info import DepsCppInfo
from conans.model.env_info import DepsEnvInfo
from conans.model.options import Options, OptionsValues, PackageOptions
from conans.model.requires import Requirements
from conans.model.user_info import DepsUserInfo
from conans.paths import RUN_LOG_NAME


def create_options(conanfile):
    try:
        package_options = PackageOptions(getattr(conanfile, "options", None))
        options = Options(package_options)

        default_options = getattr(conanfile, "default_options", None)
        if default_options:
            if isinstance(default_options, (list, tuple, dict)):
                default_values = OptionsValues(default_options)
            elif isinstance(default_options, str):
                default_values = OptionsValues.loads(default_options)
            else:
                raise ConanException("Please define your default_options as list, "
                                     "multiline string or dictionary")
            options.values = default_values
        return options
    except Exception as e:
        raise ConanException("Error while initializing options. %s" % str(e))


def create_requirements(conanfile):
    try:
        # Actual requirements of this package
        if not hasattr(conanfile, "requires"):
            return Requirements()
        else:
            if not conanfile.requires:
                return Requirements()
            if isinstance(conanfile.requires, tuple):
                return Requirements(*conanfile.requires)
            else:
                return Requirements(conanfile.requires, )
    except Exception as e:
        raise ConanException("Error while initializing requirements. %s" % str(e))


def create_settings(conanfile, settings):
    try:
        defined_settings = getattr(conanfile, "settings", None)
        if isinstance(defined_settings, str):
            defined_settings = [defined_settings]
        current = defined_settings or {}
        settings.constraint(current)
        return settings
    except Exception as e:
        raise ConanException("Error while initializing settings. %s" % str(e))


@contextmanager
def _env_and_python(conanfile):
    with environment_append(conanfile.env):
        with pythonpath(conanfile):
            yield


def get_env_context_manager(conanfile, without_python=False):
    if not conanfile.apply_env:
        return no_op()
    if without_python:
        return environment_append(conanfile.env)
    return _env_and_python(conanfile)


class ConanFile(object):
    """ The base class for all package recipes
    """

    name = None
    version = None  # Any str, can be "1.1" or whatever
    url = None  # The URL where this File is located, as github, to collaborate in package
    # The license of the PACKAGE, just a shortcut, does not replace or
    # change the actual license of the source code
    license = None
    author = None  # Main maintainer/responsible for the package, any format
    description = None
    topics = None
    homepage = None
    build_policy = None
    short_paths = False
    apply_env = True  # Apply environment variables from requires deps_env_info and profiles
    exports = None
    exports_sources = None
    generators = ["txt"]
    revision_mode = "hash"

    # Vars to control the build steps (build(), package())
    should_configure = True
    should_build = True
    should_install = True
    should_test = True
    in_local_cache = True
    develop = False

    # Defaulting the reference fields
    default_channel = None
    default_user = None

    # Settings and Options
    settings = None
    options = None
    default_options = None

    def __init__(self, output, runner, display_name="", user=None, channel=None):
        # an output stream (writeln, info, warn error)
        self.output = ScopedOutput(display_name, output)
        self.display_name = display_name
        # something that can run commands, as os.sytem
        self._conan_runner = runner
        self._conan_user = user
        self._conan_channel = channel

    def initialize(self, settings, env):
        if isinstance(self.generators, str):
            self.generators = [self.generators]
        # User defined options
        self.options = create_options(self)
        self.requires = create_requirements(self)
        self.settings = create_settings(self, settings)
        try:
            if self.settings.os_build and self.settings.os:
                self.output.writeln("*"*60, front=Color.BRIGHT_RED)
                self.output.writeln("  This package defines both 'os' and 'os_build' ",
                                    front=Color.BRIGHT_RED)
                self.output.writeln("  Please use 'os' for libraries and 'os_build'",
                                    front=Color.BRIGHT_RED)
                self.output.writeln("  only for build-requires used for cross-building",
                                    front=Color.BRIGHT_RED)
                self.output.writeln("*"*60, front=Color.BRIGHT_RED)
        except ConanException:
            pass

        # needed variables to pack the project
        self.cpp_info = None  # Will be initialized at processing time
        self.deps_cpp_info = DepsCppInfo()

        # environment variables declared in the package_info
        self.env_info = None  # Will be initialized at processing time
        self.deps_env_info = DepsEnvInfo()

        # user declared variables
        self.user_info = None
        # Keys are the package names, and the values a dict with the vars
        self.deps_user_info = DepsUserInfo()

        # user specified env variables
        self._conan_env_values = env.copy()  # user specified -e

    @property
    def env(self):
        """Apply the self.deps_env_info into a copy of self._conan_env_values (will prioritize the
        self._conan_env_values, user specified from profiles or -e first, then inherited)"""
        # Cannot be lazy cached, because it's called in configure node, and we still don't have
        # the deps_env_info objects available
        tmp_env_values = self._conan_env_values.copy()
        tmp_env_values.update(self.deps_env_info)

        ret, multiple = tmp_env_values.env_dicts(self.name)
        ret.update(multiple)
        return ret

    @property
    def channel(self):
        if not self._conan_channel:
            self._conan_channel = os.getenv("CONAN_CHANNEL") or self.default_channel
            if not self._conan_channel:
                raise ConanException("CONAN_CHANNEL environment variable not defined, "
                                     "but self.channel is used in conanfile")
        return self._conan_channel

    @property
    def user(self):
        if not self._conan_user:
            self._conan_user = os.getenv("CONAN_USERNAME") or self.default_user
            if not self._conan_user:
                raise ConanException("CONAN_USERNAME environment variable not defined, "
                                     "but self.user is used in conanfile")
        return self._conan_user

    def collect_libs(self, folder=None):
        self.output.warn("'self.collect_libs' is deprecated, "
                         "use 'tools.collect_libs(self)' instead")
        return tools.collect_libs(self, folder=folder)

    @property
    def build_policy_missing(self):
        return self.build_policy == "missing"

    @property
    def build_policy_always(self):
        return self.build_policy == "always"

    def source(self):
        pass

    def system_requirements(self):
        """ this method can be overwritten to implement logic for system package
        managers, as apt-get

        You can define self.global_system_requirements = True, if you want the installation
        to be for all packages (not depending on settings/options/requirements)
        """

    def config_options(self):
        """ modify options, probably conditioned to some settings. This call is executed
        before config_settings. E.g.
        if self.settings.os == "Windows":
            del self.options.shared  # shared/static not supported in win
        """

    def configure(self):
        """ modify settings, probably conditioned to some options. This call is executed
        after config_options. E.g.
        if self.options.header_only:
            self.settings.clear()
        This is also the place for conditional requirements
        """

    def build(self):
        """ build your project calling the desired build tools as done in the command line.
        E.g. self.run("cmake --build .") Or use the provided build helpers. E.g. cmake.build()
        """
        self.output.warn("This conanfile has no build step")

    def package(self):
        """ package the needed files from source and build folders.
        E.g. self.copy("*.h", src="src/includes", dst="includes")
        """
        self.output.warn("This conanfile has no package step")

    def package_info(self):
        """ define cpp_build_info, flags, etc
        """

    def run(self, command, output=True, cwd=None, win_bash=False, subsystem=None, msys_mingw=True,
            ignore_errors=False, run_environment=False, with_login=True):
        def _run():
            if not win_bash:
                return self._conan_runner(command, output, os.path.abspath(RUN_LOG_NAME), cwd)
            # FIXME: run in windows bash is not using output
            return tools.run_in_windows_bash(self, bashcmd=command, cwd=cwd, subsystem=subsystem,
                                             msys_mingw=msys_mingw, with_login=with_login)
        if run_environment:
            with tools.run_environment(self):
                if OSInfo().is_macos:
                    command = 'DYLD_LIBRARY_PATH="%s" %s' % (os.environ.get('DYLD_LIBRARY_PATH', ''),
                                                             command)
                retcode = _run()
        else:
            retcode = _run()

        if not ignore_errors and retcode != 0:
            raise ConanException("Error %d while executing %s" % (retcode, command))

        return retcode

    def package_id(self):
        """ modify the binary info, typically to narrow values
        e.g.: self.info.settings.compiler = "Any" => All compilers will generate same ID
        """

    def test(self):
        """ test the generated executable.
        E.g.  self.run("./example")
        """
        raise ConanException("You need to create a method 'test' in your test/conanfile.py")

    def __repr__(self):
        return self.display_name
