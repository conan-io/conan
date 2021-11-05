import os
import platform

from conan.tools.env import Environment
from conan.tools.env.environment import environment_wrap_command
from conans.cli.output import ConanOutput, ScopedOutput
from conans.errors import ConanException, ConanInvalidConfiguration
from conans.model.conf import Conf
from conans.model.dependencies import ConanFileDependencies
from conans.model.layout import Folders, Infos
from conans.model.options import Options
from conans.model.requires import Requirements
from conans.paths import RUN_LOG_NAME


class ConanFile:
    """ The base class for all package recipes
    """
    name = None
    version = None  # Any str, can be "1.1" or whatever
    user = None
    channel = None

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
    exports = None
    exports_sources = None
    generators = []
    revision_mode = "hash"

    in_local_cache = True
    develop = False

    # Settings and Options
    settings = None
    options = None
    default_options = None

    provides = None
    deprecated = None

    package_type = None
    # Run in windows bash
    win_bash = None

    def __init__(self, runner, display_name=""):
        self.display_name = display_name
        # something that can run commands, as os.sytem
        self._conan_runner = runner

        self.compatible_packages = []
        self._conan_requester = None

        self.buildenv_info = Environment()
        self.runenv_info = Environment()
        # At the moment only for build_requires, others will be ignored
        self.conf_info = Conf()
        self._conan_buildenv = None  # The profile buildenv, will be assigned initialize()
        self._conan_node = None  # access to container Node object, to access info, context, deps...

        if isinstance(self.generators, str):
            self.generators = [self.generators]
        if isinstance(self.settings, str):
            self.settings = [self.settings]
        self.requires = Requirements(getattr(self, "requires", None),
                                     getattr(self, "build_requires", None),
                                     getattr(self, "test_requires", None))

        # user declared variables
        self.user_info = None
        self._conan_dependencies = None

        if not hasattr(self, "virtualbuildenv"):  # Allow the user to override it with True or False
            self.virtualbuildenv = True
        if not hasattr(self, "virtualrunenv"):  # Allow the user to override it with True or False
            self.virtualrunenv = True

        self.env_scripts = {}  # Accumulate the env scripts generated in order

        # layout() method related variables:
        self.folders = Folders()
        self.cpp = Infos()

        self.cpp.package.includedirs = ["include"]
        self.cpp.package.libdirs = ["lib"]
        self.cpp.package.bindirs = ["bin"]
        self.cpp.package.resdirs = ["res"]
        self.cpp.package.builddirs = [""]
        self.cpp.package.frameworkdirs = ["Frameworks"]

    @property
    def output(self):
        # an output stream (writeln, info, warn error)
        scope = self.display_name
        if not scope:
            scope = self.ref if self._conan_node else ""
        return ScopedOutput(scope, ConanOutput())

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
        if not isinstance(self._conan_buildenv, Environment):
            # TODO: missing user/channel
            ref_str = "{}/{}".format(self.name, self.version)
            self._conan_buildenv = self._conan_buildenv.get_profile_env(ref_str)
        return self._conan_buildenv

    def initialize(self, settings, buildenv=None):
        # If we move this to constructor, the python_require inheritance in init fails
        # and "conan inspect" also breaks
        self.options = Options(self.options or {}, self.default_options)
        self._conan_buildenv = buildenv
        try:
            settings.constrained(self.settings)
        except Exception as e:
            raise ConanInvalidConfiguration("The recipe %s is constraining settings. %s" % (
                self.display_name, str(e)))
        self.settings = settings

    @property
    def cpp_info(self):
        return self.cpp.package

    @cpp_info.setter
    def cpp_info(self, value):
        self.cpp.package = value

    @property
    def source_folder(self):
        return self.folders.source_folder

    @source_folder.setter
    def source_folder(self, folder):
        self.folders.set_base_source(folder)

    @property
    def build_folder(self):
        return self.folders.build_folder

    @build_folder.setter
    def build_folder(self, folder):
        self.folders.set_base_build(folder)

    @property
    def package_folder(self):
        return self.folders.base_package

    @package_folder.setter
    def package_folder(self, folder):
        self.folders.set_base_package(folder)

    @property
    def install_folder(self):
        # FIXME: Remove in 2.0, no self.install_folder
        return self.folders.base_install

    @install_folder.setter
    def install_folder(self, folder):
        # FIXME: Remove in 2.0, no self.install_folder
        self.folders.set_base_install(folder)

    @property
    def generators_folder(self):
        # FIXME: Remove in 2.0, no self.install_folder
        return self.folders.generators_folder if self.folders.generators else self.install_folder

    @property
    def imports_folder(self):
        return self.folders.imports_folder

    @imports_folder.setter
    def imports_folder(self, folder):
        self.folders.set_base_imports(folder)

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
        self.output.warning("This conanfile has no build step")

    def package(self):
        """ package the needed files from source and build folders.
        E.g. self.copy("*.h", src="src/includes", dst="includes")
        """
        self.output.warning("This conanfile has no package step")

    def package_info(self):
        """ define cpp_build_info, flags, etc
        """

    def run(self, command, output=True, cwd=None, ignore_errors=False, env=None):
        # NOTE: "self.win_bash" is the new parameter "win_bash" for Conan 2.0
        if platform.system() == "Windows":
            if self.win_bash:  # New, Conan 2.0
                from conan.tools.microsoft.subsystems import run_in_windows_bash
                return run_in_windows_bash(self, command=command, cwd=cwd, env=env)
        if env is None:
            env = "conanbuild"
        wrapped_cmd = environment_wrap_command(env, command, cwd=self.generators_folder)
        retcode = self._conan_runner(wrapped_cmd, output, os.path.abspath(RUN_LOG_NAME), cwd)

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
