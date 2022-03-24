import platform

from conans.cli.output import ConanOutput, ScopedOutput
from conans.errors import ConanException
from conans.model.conf import Conf
from conans.model.dependencies import ConanFileDependencies
from conans.model.layout import Folders, Infos
from conans.model.options import Options
from conans.model.requires import Requirements


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
    tested_reference_str = None

    _conan_is_consumer = False

    def __init__(self, display_name=""):
        self.display_name = display_name
        # something that can run commands, as os.sytem

        self.compatible_packages = []
        self._conan_helpers = None
        from conan.tools.env import Environment
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
                                     getattr(self, "test_requires", None),
                                     getattr(self, "tool_requires", None))

        self.options = Options(self.options or {}, self.default_options)

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

    def serialize(self):
        result = {}
        for a in ("url", "license", "author", "description", "topics", "homepage", "build_policy",
                  "revision_mode", "provides", "deprecated", "win_bash"):
            v = getattr(self, a)
            if v is not None:
                result[a] = v
        result["package_type"] = str(self.package_type)
        result["settings"] = self.settings.serialize()
        if hasattr(self, "python_requires"):
            result["python_requires"] = [r.repr_notime() for r in self.python_requires.all_refs()]
        result.update(self.options.serialize())  # FIXME: The options contain an "options" already
        result["source_folder"] = self.source_folder
        result["build_folder"] = self.build_folder
        result["package_folder"] = self.package_folder
        return result

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
        from conan.tools.env import Environment
        if not isinstance(self._conan_buildenv, Environment):
            self._conan_buildenv = self._conan_buildenv.get_profile_env(self.ref,
                                                                        self._conan_is_consumer)
        return self._conan_buildenv

    @property
    def cpp_info(self):
        return self.cpp.package

    @cpp_info.setter
    def cpp_info(self, value):
        self.cpp.package = value

    @property
    def source_folder(self):
        return self.folders.source_folder

    @property
    def base_source_folder(self):
        """ returns the base_source folder, that is the containing source folder in the cache
        irrespective of the layout() and where the final self.source_folder (computed with the
        layout()) points.
        This can be necessary in the source() or build() methods to locate where exported sources
        are, like patches or entire files that will be used to complete downloaded sources"""
        return self.folders._base_source

    @property
    def build_folder(self):
        return self.folders.build_folder

    @property
    def package_folder(self):
        return self.folders.base_package

    @property
    def generators_folder(self):
        return self.folders.generators_folder

    def source(self):
        pass

    def system_requirements(self):
        """ this method can be overwritten to implement logic for system package
        managers, as apt-get
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
        E.g. copy(self, "*.h", os.path.join(self.source_folder, "src/includes"), os.path.join(self.package_folder, "includes"))
        """
        self.output.warning("This conanfile has no package step")

    def package_info(self):
        """ define cpp_build_info, flags, etc
        """

    def run(self, command, stdout=None, cwd=None, ignore_errors=False, env=None, quiet=False,
            shell=True):
        # NOTE: "self.win_bash" is the new parameter "win_bash" for Conan 2.0
        command = self._conan_helpers.cmd_wrapper.wrap(command)
        if platform.system() == "Windows":
            if self.win_bash:  # New, Conan 2.0
                from conans.client.subsystems import run_in_windows_bash
                return run_in_windows_bash(self, command=command, cwd=cwd, env=env)
        if env is None:
            env = "conanbuild"
        from conan.tools.env.environment import environment_wrap_command
        wrapped_cmd = environment_wrap_command(env, command, cwd=self.generators_folder)
        from conans.util.runners import conan_run
        ConanOutput().writeln(f"{self.display_name}: RUN: {command if not quiet else '*hidden*'}")
        retcode = conan_run(wrapped_cmd, cwd=cwd, stdout=stdout, shell=shell)

        if not ignore_errors and retcode != 0:
            raise ConanException("Error %d while executing" % retcode)

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

    def set_deploy_folder(self, deploy_folder):
        self.cpp_info.deploy_base_folder(self.package_folder, deploy_folder)
        self.folders.set_base_package(deploy_folder)
