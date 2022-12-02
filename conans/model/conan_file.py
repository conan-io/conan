import os
from pathlib import Path

from conan.api.output import ConanOutput
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

    #: String corresponding to the ``<name>`` at the recipe reference ``<name>/version@user/channel``
    name = None

    #: String corresponding to the ``<version>`` at the recipe reference
    #: ``name/<version>@user/channel``
    version = None  # Any str, can be "1.1" or whatever

    #: String corresponding to the ``<user>`` at the recipe reference ``name/version@<user>/channel``
    user = None

    #: String corresponding to the ``<channel>`` at the recipe reference
    #: ``name/version@user/<channel>``.
    channel = None

    #: URL of the package repository, i.e. not necessarily of the original source code.
    #: Recommended, but not mandatory attribute.
    url = None  # The URL where this File is located, as github, to collaborate in package

    #: License of the **target** source code and binaries, i.e. the code
    #: that is being packaged, not the ``conanfile.py`` itself.
    #: Can contain several, comma separated licenses. It is a text string, so it can
    #: contain any text, but it is strongly recommended that recipes of Open Source projects use
    #: `SPDX <https://spdx.dev>`_ identifiers from the `SPDX license list
    #: <https://spdx.dev/licenses/>`_
    license = None

    #: Main maintainer/responsible for the package, any format. This is an optional attribute.
    author = None

    #: Description of the package and any information that might be useful for the consumers.
    #: The first line might be used as a short description of the package.
    description = None

    #: Tags to group related packages together and describe what the code is about.
    #: Used as a search filter in conan-center. Optional attribute. It should be a tuple of strings.
    topics = None

    #: The home web page of the library being packaged.
    homepage = None

    #: Controls when the current package is built during a ``conan install``.
    #: The allowed values are:
    #:
    #: - ``"missing"``: Conan builds it from source if there is no binary available.
    #: - ``"never"``: This package cannot be built from sources, it is always created with
    #:   ``conan export-pkg``
    #: - ``None`` (default value): This package won't be build unless the policy is specified
    #:   in the command line (e.g ``--build=foo*``)
    build_policy = None

    #: Controls when the current package built binaries are uploaded or not
    #:
    #: - ``"skip"``: The precompiled binaries are not uploaded. This is useful for "installer"
    #:   packages that just download and unzip something heavy (e.g. android-ndk), and is useful
    #:   together with the ``build_policy = "missing"``
    upload_policy = None

    #: List or tuple of strings with `file names` or
    #: `fnmatch <https://docs.python.org/3/library/fnmatch.html>`_ patterns that should be exported
    #: and stored side by side with the *conanfile.py* file to make the recipe work:
    #: other python files that the recipe will import, some text file with data to read,...
    exports = None

    #: List or tuple of strings with file names or
    #: `fnmatch <https://docs.python.org/3/library/fnmatch.html>`_ patterns that should be exported
    #: and will be available to generate the package. Unlike the ``exports`` attribute, these files
    #: shouldn’t be used by the ``conanfile.py`` Python code, but to compile the library or generate
    #: the final package. And, due to its purpose, these files will only be retrieved if requested
    #: binaries are not available or the user forces Conan to compile from sources.
    exports_sources = None

    #: List or tuple of strings with names of generators.
    generators = []
    revision_mode = "hash"

    # Settings and Options

    #: List of strings with the first level settings (from ``settings.yml``) that the recipe
    #: need, because:
    #:
    #:  - They are read for building (e.g: `if self.settings.compiler == "gcc"`)
    #:  - They affect the ``package_id``. If a value of the declared setting changes, the
    #:    ``package_id`` has to be different.
    settings = None

    #: Dictionary with traits that affects only the current recipe, where the key is the
    #: option name and the value is a list of different values that the option can take.
    #: By default any value change in an option, changes the ``package_id``. Check the
    #: ``default_options`` field to define default values for the options.
    options = None

    #: The attribute ``default_options`` defines the default values for the options, both for the
    #: current recipe and for any requirement.
    #: This attribute should be defined as a python dictionary.
    default_options = None

    #: This attribute declares that the recipe provides the same functionality as other recipe(s).
    #: The attribute is usually needed if two or more libraries implement the same API to prevent
    #: link-time and run-time conflicts (ODR violations). One typical situation is forked libraries.
    #: Some examples are:
    #:
    #: - `LibreSSL <https://www.libressl.org/>`__, `BoringSSL <https://boringssl.googlesource.com/boringssl/>`__ and `OpenSSL <https://www.openssl.org/>`__
    #: - `libav <https://en.wikipedia.org/wiki/Libav>`__ and `ffmpeg <https://ffmpeg.org/>`__
    #: - `MariaDB client <https://downloads.mariadb.org/client-native>`__ and `MySQL client <https://dev.mysql.com/downloads/c-api/>`__
    provides = None

    #: This attribute declares that the recipe is deprecated, causing a user-friendly warning
    #: message to be emitted whenever it is used
    deprecated = None

    #: Optional.
    #: Declaring the ``package_type`` will help Conan:
    #:
    #:  - To choose better the default ``package_id_mode`` for each dependency, that is, how a change
    #:    in a dependency should affect the ``package_id`` to the current package.
    #:  - Which information from the dependencies should be propagated to the consumers, like
    #:    headers, libraries, runtime information...
    #:
    #: The valid values are:
    #:
    #:     - **application**: The package is an application.
    #:     - **library**: The package is a generic library. It will try to determine
    #:       the type of library (from ``shared-library``, ``static-library``, ``header-library``)
    #:       reading the ``self.options.shared`` (if declared) and the ``self.options.header_only``
    #:     - **shared-library**: The package is a shared library.
    #:     - **static-library**: The package is a static library.
    #:     - **header-library**: The package is a header only library.
    #:     - **build-scripts**: The package only contains build scripts.
    #:     - **python-require**: The package is a python require.
    #:     - **unknown**: The type of the package is unknown.
    package_type = None

    #: When ``True`` it enables the new run in a subsystem bash in Windows mechanism.
    win_bash = None

    #: When ``True`` it enables running commands in the ``"run"`` scope, to run them inside a bash shell.
    win_bash_run = None  # For run scope

    tested_reference_str = None

    _conan_is_consumer = False

    # #### Requirements

    #: List or tuple of strings for regular dependencies in the host context, like a library.
    requires = None

    #: List or tuple of strings for dependencies. Represents a build tool like "cmake". If there is
    #: an existing pre-compiled binary for the current package, the binaries for the tool_require
    #: won't be retrieved. They cannot conflict.
    tool_requires = None

    #: List or tuple of strings for dependencies. Generic type of build dependencies that are not
    #: applications (nothing runs), like build scripts. If there is
    #: an existing pre-compiled binary for the current package, the binaries for the build_require
    #: won't be retrieved. They cannot conflict.
    build_requires = None

    #: List or tuple of strings for dependencies in the host context only. Represents a test tool
    #: like "gtest". Used when the current package is built from sources.
    #: They don't propagate information to the downstream consumers. If there is
    #: an existing pre-compiled binary for the current package, the binaries for the test_require
    #: won't be retrieved. They cannot conflict.
    test_requires = None

    #: The attribute ``no_copy_source`` tells the recipe that the source code will not be copied from
    #: the ``source_folder`` to the ``build_folder``. This is mostly an optimization for packages
    #: with large source codebases or header-only, to avoid extra copies.
    no_copy_source = False

    #: The folder where the recipe *conanfile.py* is stored, either in the local folder or in
    #: the cache. This is useful in order to access files that are exported along with the recipe,
    #: or the origin folder when exporting files in ``export(self)`` and ``export_sources(self)``
    #: methods.
    recipe_folder = None

    #: Object storing all the information needed by the consumers
    #: of a package: include directories, library names, library paths... Both for editable
    #: and regular packages in the cache. It is only available at the ``layout()`` method.
    #:
    #:  - ``self.cpp.package``: For a regular package being used from the Conan cache. Same as
    #:    declaring ``self.cpp_info`` at the ``package_info()`` method.
    #:  - ``self.cpp.source``: For "editable" packages, to describe the artifacts under
    #:    ``self.source_folder``
    #:  - ``self.cpp.build``: For "editable" packages, to describe the artifacts under
    #:    ``self.build_folder``.
    #:
    cpp = None

    #: For the dependant recipes, the declared environment variables will be present during the
    #: build process. Should be only filled in the ``package_info()`` method.
    buildenv_info = None

    #: For the dependant recipes, the declared environment variables will be present at runtime.
    #: Should be only filled in the ``package_info()`` method.
    runenv_info = None

    #: Configuration variables to be passed to the dependant recipes.
    #: Should be only filled in the ``package_info()`` method.
    conf_info = None

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
        self.info = None
        self._conan_buildenv = None  # The profile buildenv, will be assigned initialize()
        self._conan_runenv = None
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
        self.user_info = MockInfoProperty("user_info")
        self.env_info = MockInfoProperty("env_info")
        self._conan_dependencies = None

        if not hasattr(self, "virtualbuildenv"):  # Allow the user to override it with True or False
            self.virtualbuildenv = True
        if not hasattr(self, "virtualrunenv"):  # Allow the user to override it with True or False
            self.virtualrunenv = True

        self.env_scripts = {}  # Accumulate the env scripts generated in order

        # layout() method related variables:
        self.folders = Folders()
        self.cpp = Infos()
        self.layouts = Layouts()

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
        result["options"] = self.options.serialize()
        result["source_folder"] = self.source_folder
        result["build_folder"] = self.build_folder
        result["package_folder"] = self.package_folder
        result["cpp_info"] = self.cpp_info.serialize()
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
        command = self._conan_helpers.cmd_wrapper.wrap(command)
        if env == "":  # This default allows not breaking for users with ``env=None`` indicating
            # they don't want any env-file applied
            env = "conanbuild" if scope == "build" else "conanrun"

        env = [env] if env and isinstance(env, str) else (env or [])
        assert isinstance(env, list), "env argument to ConanFile.run() should be a list"
        envfiles_folder = self.generators_folder or os.getcwd()
        wrapped_cmd = command_env_wrapper(self, command, env, envfiles_folder=envfiles_folder)
        from conans.util.runners import conan_run
        ConanOutput().writeln(f"{self.display_name}: RUN: {command if not quiet else '*hidden*'}")
        retcode = conan_run(wrapped_cmd, cwd=cwd, stdout=stdout, shell=shell)

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
