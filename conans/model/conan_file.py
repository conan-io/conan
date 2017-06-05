from conans.model.options import Options, PackageOptions, OptionsValues
from conans.model.requires import Requirements
from conans.model.build_info import DepsCppInfo
from conans import tools  # @UnusedImport KEEP THIS! Needed for pyinstaller to copy to exe.
from conans.errors import ConanException
from conans.model.env_info import DepsEnvInfo, EnvValues
import os
from conans.paths import RUN_LOG_NAME


def create_options(conanfile):
    try:
        package_options = PackageOptions(getattr(conanfile, "options", None))
        options = Options(package_options)

        default_options = getattr(conanfile, "default_options", None)
        if default_options:
            if isinstance(default_options, (list, tuple)):
                default_values = OptionsValues(default_options)
            elif isinstance(default_options, str):
                default_values = OptionsValues.loads(default_options)
            else:
                raise ConanException("Please define your default_options as list or "
                                     "multiline string")
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


def create_exports(conanfile):
    if not hasattr(conanfile, "exports"):
        return None
    else:
        if isinstance(conanfile.exports, str):
            return (conanfile.exports, )
        return conanfile.exports


def create_exports_sources(conanfile):
    if not hasattr(conanfile, "exports_sources"):
        return None
    else:
        if isinstance(conanfile.exports_sources, str):
            return (conanfile.exports_sources, )
        return conanfile.exports_sources


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
    build_policy = None
    short_paths = False

    def __init__(self, output, runner, settings, conanfile_directory, user=None, channel=None):
        # User defined generators
        self.generators = self.generators if hasattr(self, "generators") else ["txt"]
        if isinstance(self.generators, str):
            self.generators = [self.generators]

        # User defined options
        self.options = create_options(self)
        self.requires = create_requirements(self)
        self.settings = create_settings(self, settings)
        self.exports = create_exports(self)
        self.exports_sources = create_exports_sources(self)
        # needed variables to pack the project
        self.cpp_info = None  # Will be initialized at processing time
        self.deps_cpp_info = DepsCppInfo()

        # environment variables declared in the package_info
        self.env_info = None  # Will be initialized at processing time
        self.deps_env_info = DepsEnvInfo()

        self.copy = None  # initialized at runtime

        # an output stream (writeln, info, warn error)
        self.output = output
        # something that can run commands, as os.sytem
        self._runner = runner

        self._conanfile_directory = conanfile_directory
        self.package_folder = None  # Assigned at runtime
        self._scope = None

        # user specified env variables
        self._env_values = EnvValues()  # Updated at runtime, user specified -e
        self._user = user
        self._channel = channel

    @property
    def env(self):
        simple, multiple = self._env_values.env_dicts(self.name)
        simple.update(multiple)
        return simple

    @property
    def channel(self):
        if not self._channel:
            self._channel = os.getenv("CONAN_CHANNEL")
            if not self._channel:
                raise ConanException("CONAN_CHANNEL environment variable not defined, "
                                     "but self.channel is used in conanfile")
        return self._channel

    @property
    def user(self):
        if not self._user:
            self._user = os.getenv("CONAN_USERNAME")
            if not self._user:
                raise ConanException("CONAN_USERNAME environment variable not defined, "
                                     "but self.user is used in conanfile")
        return self._user

    def collect_libs(self, folder="lib"):
        if not self.package_folder:
            return []
        lib_folder = os.path.join(self.package_folder, folder)
        if not os.path.exists(lib_folder):
            self.output.warn("Package folder doesn't exist, can't collect libraries")
            return []
        files = os.listdir(lib_folder)
        result = []
        for f in files:
            name, ext = os.path.splitext(f)
            if ext in (".so", ".lib", ".a", ".dylib"):
                if ext != ".lib" and name.startswith("lib"):
                    name = name[3:]
                result.append(name)
        return result

    @property
    def scope(self):
        return self._scope

    @scope.setter
    def scope(self, value):
        self._scope = value
        if value.dev:
            self.requires.allow_dev = True
            try:
                if hasattr(self, "dev_requires"):
                    if isinstance(self.dev_requires, tuple):
                        self.requires.add_dev(*self.dev_requires)
                    else:
                        self.requires.add_dev(self.dev_requires, )
            except Exception as e:
                raise ConanException("Error while initializing dev_requirements. %s" % str(e))

    @property
    def conanfile_directory(self):
        return self._conanfile_directory

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

    def imports(self):
        pass

    def build(self):
        self.output.warn("This conanfile has no build step")

    def package(self):
        self.output.warn("This conanfile has no package step")

    def package_info(self):
        """ define cpp_build_info, flags, etc
        """

    def run(self, command, output=True, cwd=None):
        """ runs such a command in the folder the Conan
        is defined
        """
        retcode = self._runner(command, output, os.path.abspath(RUN_LOG_NAME),  cwd)
        if retcode != 0:
            raise ConanException("Error %d while executing %s" % (retcode, command))

    def package_id(self):
        """ modify the conans info, typically to narrow values
        eg.: conaninfo.package_references = []
        """

    def test(self):
        raise ConanException("You need to create a method 'test' in your test/conanfile.py")

    def __repr__(self):
        if self.name and self.version and self._channel and self._user:
            return "%s/%s@%s/%s" % (self.name, self.version, self.user, self.channel)
        elif self.name and self.version:
            return "%s/%s@PROJECT" % (self.name, self.version)
        else:
            return "PROJECT"

