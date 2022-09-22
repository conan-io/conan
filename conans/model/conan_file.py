import os
import platform
from contextlib import contextmanager
from pathlib import Path

import six
from six import string_types


from conans.client import tools
from conans.client.output import ScopedOutput
from conans.client.subsystems import command_env_wrapper
from conans.client.tools.env import environment_append, no_op, pythonpath
from conans.client.tools.oss import OSInfo
from conans.errors import ConanException, ConanInvalidConfiguration
from conans.model.build_info import DepsCppInfo
from conans.model.conf import Conf
from conans.model.dependencies import ConanFileDependencies
from conans.model.env_info import DepsEnvInfo
from conans.model.layout import Folders, Infos
from conans.model.new_build_info import from_old_cppinfo
from conans.model.options import Options, OptionsValues, PackageOptions
from conans.model.requires import Requirements
from conans.model.user_info import DepsUserInfo
from conans.paths import RUN_LOG_NAME
from conans.util.conan_v2_mode import conan_v2_error


def create_options(conanfile):
    try:
        package_options = PackageOptions(getattr(conanfile, "options", None))
        options = Options(package_options)

        default_options = getattr(conanfile, "default_options", None)
        if default_options:
            if isinstance(default_options, dict):
                default_values = OptionsValues(default_options)
            elif isinstance(default_options, (list, tuple)):
                conan_v2_error("Declare 'default_options' as a dictionary")
                default_values = OptionsValues(default_options)
            elif isinstance(default_options, six.string_types):
                conan_v2_error("Declare 'default_options' as a dictionary")
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
            if isinstance(conanfile.requires, (tuple, list)):
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
        raise ConanInvalidConfiguration("The recipe %s is constraining settings. %s" % (
                                        conanfile.display_name, str(e)))


@contextmanager
def _env_and_python(conanfile):
    with environment_append(conanfile.env):
        # FIXME Conan 2.0, Remove old ways of reusing python code
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

    provides = None
    deprecated = None

    # Folders
    folders = None
    patterns = None

    # Run in windows bash
    win_bash = None
    tested_reference_str = None

    def __init__(self, output, runner, display_name="", user=None, channel=None):
        # an output stream (writeln, info, warn error)
        self.output = ScopedOutput(display_name, output)
        self.display_name = display_name
        # something that can run commands, as os.sytem
        self._conan_runner = runner
        self._conan_user = user
        self._conan_channel = channel

        self.compatible_packages = []
        self._conan_using_build_profile = False
        self._conan_requester = None
        from conan.tools.env import Environment
        self.buildenv_info = Environment()
        self.runenv_info = Environment()
        # At the moment only for build_requires, others will be ignored
        self.conf_info = Conf()
        self._conan_buildenv = None  # The profile buildenv, will be assigned initialize()
        self._conan_node = None  # access to container Node object, to access info, context, deps...
        self._conan_new_cpp_info = None   # Will be calculated lazy in the getter
        self._conan_dependencies = None

        self.env_scripts = {}  # Accumulate the env scripts generated in order

        # layout() method related variables:
        self.folders = Folders()
        self.cpp = Infos()

        self.cpp.package.includedirs = ["include"]
        self.cpp.package.libdirs = ["lib"]
        self.cpp.package.bindirs = ["bin"]
        self.cpp.package.resdirs = []
        self.cpp.package.builddirs = [""]
        self.cpp.package.frameworkdirs = []

    @property
    def context(self):
        return self._conan_node.context

    @property
    def dependencies(self):
        # Caching it, this object is requested many times
        if self._conan_dependencies is None:
            self._conan_dependencies = ConanFileDependencies.from_node(self._conan_node)
        return self._conan_dependencies

    @property
    def ref(self):
        return self._conan_node.ref

    @property
    def pref(self):
        return self._conan_node.pref

    @property
    def buildenv(self):
        # Lazy computation of the package buildenv based on the profileone
        from conan.tools.env import Environment
        if not isinstance(self._conan_buildenv, Environment):
            # TODO: missing user/channel
            ref_str = "{}/{}".format(self.name, self.version)
            self._conan_buildenv = self._conan_buildenv.get_profile_env(ref_str)
        return self._conan_buildenv

    def initialize(self, settings, env, buildenv=None):
        self._conan_buildenv = buildenv
        if isinstance(self.generators, str):
            self.generators = [self.generators]
        # User defined options
        self.options = create_options(self)
        self.requires = create_requirements(self)
        self.settings = create_settings(self, settings)

        conan_v2_error("Setting 'cppstd' is deprecated in favor of 'compiler.cppstd',"
                       " please update your recipe.", 'cppstd' in self.settings.fields)

        # needed variables to pack the project
        self.cpp_info = None  # Will be initialized at processing time
        self._conan_dep_cpp_info = None  # Will be initialized at processing time
        self.deps_cpp_info = DepsCppInfo()

        # environment variables declared in the package_info
        self.env_info = None  # Will be initialized at processing time
        self.deps_env_info = DepsEnvInfo()

        # user declared variables
        self.user_info = None
        # Keys are the package names (only 'host' if different contexts)
        self.deps_user_info = DepsUserInfo()

        # user specified env variables
        self._conan_env_values = env.copy()  # user specified -e

        if self.description is not None and not isinstance(self.description, six.string_types):
            raise ConanException("Recipe 'description' must be a string.")

        if not hasattr(self, "virtualbuildenv"):  # Allow the user to override it with True or False
            self.virtualbuildenv = True
        if not hasattr(self, "virtualrunenv"):  # Allow the user to override it with True or False
            self.virtualrunenv = True

    @property
    def new_cpp_info(self):
        if not self._conan_new_cpp_info:
            self._conan_new_cpp_info = from_old_cppinfo(self.cpp_info)
            # The new_cpp_info will be already absolute paths if layout() is defined
            if self.package_folder is not None:  # to not crash when editable and layout()
                self._conan_new_cpp_info.set_relative_base_folder(self.package_folder)
        return self._conan_new_cpp_info

    @property
    def source_folder(self):
        return self.folders.source_folder

    @property
    def source_path(self) -> Path:
        assert self.source_folder is not None, "`source_folder` is `None`"
        return Path(self.source_folder)

    @property
    def export_sources_folder(self):
        """points to the base source folder when calling source() and to the cache export sources
        folder while calling the exports_sources() method. Prepared in case we want to introduce a
        'no_copy_export_sources' and point to the right location always."""
        return self.folders.base_export_sources

    @property
    def export_sources_path(self) -> Path:
        assert self.export_sources_folder is not None, "`export_sources_folder` is `None`"
        return Path(self.export_sources_folder)

    @property
    def export_folder(self):
        return self.folders.base_export

    @property
    def export_path(self) -> Path:
        assert self.export_folder is not None, "`export_folder` is `None`"
        return Path(self.export_folder)

    @property
    def build_folder(self):
        return self.folders.build_folder

    @property
    def build_path(self) -> Path:
        assert self.build_folder is not None, "`build_folder` is `None`"
        return Path(self.build_folder)

    @property
    def package_folder(self):
        return self.folders.base_package

    @property
    def package_path(self) -> Path:
        assert self.package_folder is not None, "`package_folder` is `None`"
        return Path(self.package_folder)

    @property
    def install_folder(self):
        # FIXME: Remove in 2.0, no self.install_folder
        return self.folders.base_install

    @property
    def generators_folder(self):
        # FIXME: Remove in 2.0, no self.install_folder
        return self.folders.generators_folder if self.folders.generators else self.install_folder

    @property
    def generators_path(self) -> Path:
        assert self.generators_folder is not None, "`generators_folder` is `None`"
        return Path(self.generators_folder)

    @property
    def imports_folder(self):
        return self.folders.imports_folder

    @property
    def env(self):
        """Apply the self.deps_env_info into a copy of self._conan_env_values (will prioritize the
        self._conan_env_values, user specified from profiles or -e first, then inherited)"""
        # Cannot be lazy cached, because it's called in configure node, and we still don't have
        # the deps_env_info objects available
        tmp_env_values = self._conan_env_values.copy()
        tmp_env_values.update(self.deps_env_info)
        ret, multiple = tmp_env_values.env_dicts(self.name, self.version, self._conan_user,
                                                 self._conan_channel)
        ret.update(multiple)
        return ret

    @property
    def channel(self):
        if not self._conan_channel:
            _env_channel = os.getenv("CONAN_CHANNEL")
            conan_v2_error("Environment variable 'CONAN_CHANNEL' is deprecated", _env_channel)
            self._conan_channel = _env_channel or self.default_channel
            if not self._conan_channel:
                raise ConanException("channel not defined, but self.channel is used in conanfile")
        return self._conan_channel

    @property
    def user(self):
        if not self._conan_user:
            _env_username = os.getenv("CONAN_USERNAME")
            conan_v2_error("Environment variable 'CONAN_USERNAME' is deprecated", _env_username)
            self._conan_user = _env_username or self.default_user
            if not self._conan_user:
                raise ConanException("user not defined, but self.user is used in conanfile")
        return self._conan_user

    def collect_libs(self, folder=None):
        conan_v2_error("'self.collect_libs' is deprecated, use 'tools.collect_libs(self)' instead")
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
            ignore_errors=False, run_environment=False, with_login=True, env="conanbuild"):
        # NOTE: "self.win_bash" is the new parameter "win_bash" for Conan 2.0

        def _run(cmd, _env):
            # FIXME: run in windows bash is not using output
            if platform.system() == "Windows":
                if win_bash:
                    return tools.run_in_windows_bash(self, bashcmd=cmd, cwd=cwd, subsystem=subsystem,
                                                     msys_mingw=msys_mingw, with_login=with_login)
            envfiles_folder = self.generators_folder or os.getcwd()
            _env = [_env] if _env and isinstance(_env, str) else []
            wrapped_cmd = command_env_wrapper(self, cmd, _env, envfiles_folder=envfiles_folder)
            return self._conan_runner(wrapped_cmd, output, os.path.abspath(RUN_LOG_NAME), cwd)

        if run_environment:
            # When using_build_profile the required environment is already applied through
            # 'conanfile.env' in the contextmanager 'get_env_context_manager'
            with tools.run_environment(self) if not self._conan_using_build_profile else no_op():
                if OSInfo().is_macos and isinstance(command, string_types):
                    # Security policy on macOS clears this variable when executing /bin/sh. To
                    # keep its value, set it again inside the shell when running the command.
                    command = 'DYLD_LIBRARY_PATH="%s" DYLD_FRAMEWORK_PATH="%s" %s' % \
                              (os.environ.get('DYLD_LIBRARY_PATH', ''),
                               os.environ.get("DYLD_FRAMEWORK_PATH", ''),
                               command)
                retcode = _run(command, env)
        else:
            retcode = _run(command, env)

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
