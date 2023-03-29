import os
from pathlib import Path

from conan.api.output import ConanOutput, Color
from conans.client.subsystems import command_env_wrapper
from conans.errors import ConanException
from conans.model.build_info import MockInfoProperty
from conans.model.conf import Conf
from conans.model.dependencies import ConanFileDependencies
from conans.model.layout import Folders, Infos, Layouts
from conans.model.options import Options

from conans.model.requires import Requirements


class ConanFile:
    """
    The base class for all package recipes
    """

    # Reference
    name = None
    version = None  # Any str, can be "1.1" or whatever
    user = None
    channel = None

    # Metadata
    url = None  # The URL where this File is located, as github, to collaborate in package
    license = None
    author = None
    description = None
    topics = None
    homepage = None

    build_policy = None
    upload_policy = None

    exports = None
    exports_sources = None

    generators = []
    revision_mode = "hash"

    # Binary model: Settings and Options
    settings = None
    options = None
    default_options = None
    package_type = None

    provides = None
    deprecated = None

    win_bash = None
    win_bash_run = None  # For run scope

    _conan_is_consumer = False

    # #### Requirements
    requires = None
    tool_requires = None
    build_requires = None
    test_requires = None
    tested_reference_str = None

    no_copy_source = False
    recipe_folder = None

    # Package information
    cpp = None
    buildenv_info = None
    runenv_info = None
    conf_info = None

    def __init__(self, display_name=""):
        self.display_name = display_name
        # something that can run commands, as os.sytem

        self._conan_helpers = None
        from conan.tools.env import Environment
        self.buildenv_info = Environment()
        self.runenv_info = Environment()
        # At the moment only for build_requires, others will be ignored
        self.conf_info = Conf()
        self.info = None
        self._conan_buildenv = None  # The profile buildenv, will be assigned initialize()
        self._conan_runenv = None
        self._conan_node = None  # access to container Node object, to access info, context, deps...

        if isinstance(self.generators, str):
            self.generators = [self.generators]
        if isinstance(self.settings, str):
            self.settings = [self.settings]
        self.requires = Requirements(self.requires, self.build_requires, self.test_requires,
                                     self.tool_requires)

        self.options = Options(self.options or {}, self.default_options)

        if isinstance(self.topics, str):
            self.topics = [self.topics]
        if isinstance(self.provides, str):
            self.provides = [self.provides]

        # user declared variables
        self.user_info = MockInfoProperty("user_info")
        self.env_info = MockInfoProperty("env_info")
        self._conan_dependencies = None

        if not hasattr(self, "virtualbuildenv"):  # Allow the user to override it with True or False
            self.virtualbuildenv = True
        if not hasattr(self, "virtualrunenv"):  # Allow the user to override it with True or False
            self.virtualrunenv = True

        self.env_scripts = {}  # Accumulate the env scripts generated in order
        self.system_requires = {}  # Read only, internal {"apt": []}

        # layout() method related variables:
        self.folders = Folders()
        self.cpp = Infos()
        self.layouts = Layouts()

    def serialize(self):
        result = {}

        for a in ("url", "license", "author", "description", "topics", "homepage", "build_policy",
                  "upload_policy",
                  "revision_mode", "provides", "deprecated", "win_bash", "win_bash_run"):
            v = getattr(self, a)
            if v is not None:
                result[a] = v

        result["package_type"] = str(self.package_type)
        result["settings"] = self.settings.serialize()
        result["options"] = self.options.serialize()

        if hasattr(self, "python_requires"):
            result["python_requires"] = [r.repr_notime() for r in self.python_requires.all_refs()]
        result["system_requires"] = self.system_requires

        result["recipe_folder"] = self.recipe_folder
        result["source_folder"] = self.source_folder
        result["build_folder"] = self.build_folder
        result["generators_folder"] = self.generators_folder
        result["package_folder"] = self.package_folder

        result["cpp_info"] = self.cpp_info.serialize()
        result["label"] = self.display_name
        return result

    @property
    def output(self):
        # an output stream (writeln, info, warn error)
        scope = self.display_name
        if not scope:
            scope = self.ref if self._conan_node else ""
        return ConanOutput(scope=scope)

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
    def runenv(self):
        # Lazy computation of the package runenv based on the profile one
        from conan.tools.env import Environment
        if not isinstance(self._conan_runenv, Environment):
            self._conan_runenv = self._conan_runenv.get_profile_env(self.ref,
                                                                    self._conan_is_consumer)
        return self._conan_runenv

    @property
    def cpp_info(self):
        """
        Same as using ``self.cpp.package`` in the ``layout()`` method. Use it if you need to read
        the ``package_folder`` to locate the already located artifacts.
        """
        return self.cpp.package

    @cpp_info.setter
    def cpp_info(self, value):
        self.cpp.package = value

    @property
    def source_folder(self):
        """
        The folder in which the source code lives. The path is built joining the base directory
        (a cache directory when running in the cache or the ``output folder`` when running locally)
        with the value of ``folders.source`` if declared in the ``layout()`` method.

        :return: A string with the path to the source folder.
        """
        return self.folders.source_folder

    @property
    def source_path(self) -> Path:
        assert self.source_folder is not None, "`source_folder` is `None`"
        return Path(self.source_folder)

    @property
    def export_sources_folder(self):
        """
        The value depends on the method you access it:

            - At ``source(self)``: Points to the base source folder (that means self.source_folder but
              without taking into account the ``folders.source`` declared in the ``layout()`` method).
              The declared `exports_sources` are copied to that base source folder always.
            - At ``exports_sources(self)``: Points to the folder in the cache where the export sources
              have to be copied.

        :return: A string with the mentioned path.
        """
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
        """
        The folder used to build the source code. The path is built joining the base directory (a cache
        directory when running in the cache or the ``output folder`` when running locally) with
        the value of ``folders.build`` if declared in the ``layout()`` method.

        :return: A string with the path to the build folder.
        """
        return self.folders.build_folder

    @property
    def recipe_metadata_folder(self):
        return self.folders.recipe_metadata_folder

    @property
    def pkg_metadata_folder(self):
        return self.folders.pkg_metadata_folder

    @property
    def build_path(self) -> Path:
        assert self.build_folder is not None, "`build_folder` is `None`"
        return Path(self.build_folder)

    @property
    def package_folder(self):
        """
        The folder to copy the final artifacts for the binary package. In the local cache a package
        folder is created for every different package ID.

        :return: A string with the path to the package folder.
        """
        return self.folders.base_package

    @property
    def generators_folder(self):
        return self.folders.generators_folder

    @property
    def package_path(self) -> Path:
        assert self.package_folder is not None, "`package_folder` is `None`"
        return Path(self.package_folder)

    @property
    def generators_path(self) -> Path:
        assert self.generators_folder is not None, "`generators_folder` is `None`"
        return Path(self.generators_folder)

    def run(self, command, stdout=None, cwd=None, ignore_errors=False, env="", quiet=False,
            shell=True, scope="build"):
        # NOTE: "self.win_bash" is the new parameter "win_bash" for Conan 2.0
        command = self._conan_helpers.cmd_wrapper.wrap(command, conanfile=self)
        if env == "":  # This default allows not breaking for users with ``env=None`` indicating
            # they don't want any env-file applied
            env = "conanbuild" if scope == "build" else "conanrun"

        env = [env] if env and isinstance(env, str) else (env or [])
        assert isinstance(env, list), "env argument to ConanFile.run() should be a list"
        envfiles_folder = self.generators_folder or os.getcwd()
        wrapped_cmd = command_env_wrapper(self, command, env, envfiles_folder=envfiles_folder)
        from conans.util.runners import conan_run
        ConanOutput().writeln(f"{self.display_name}: RUN: {command if not quiet else '*hidden*'}",
                              fg=Color.BRIGHT_BLUE)
        retcode = conan_run(wrapped_cmd, cwd=cwd, stdout=stdout, shell=shell)
        ConanOutput().writeln("")

        if not ignore_errors and retcode != 0:
            raise ConanException("Error %d while executing" % retcode)

        return retcode

    def __repr__(self):
        return self.display_name

    def set_deploy_folder(self, deploy_folder):
        self.cpp_info.deploy_base_folder(self.package_folder, deploy_folder)
        self.buildenv_info.deploy_base_folder(self.package_folder, deploy_folder)
        self.runenv_info.deploy_base_folder(self.package_folder, deploy_folder)
        self.folders.set_base_package(deploy_folder)
