from conans.model.options import Options, PackageOptions, OptionsValues
from conans.model.requires import Requirements
from conans.model.build_info import DepsCppInfo
from conans import tools  # @UnusedImport KEEP THIS! Needed for pyinstaller to copy to exe.
from conans.errors import ConanException


def create_options(conanfile):
    try:
        package_options = PackageOptions(getattr(conanfile, "options", None))
        options = Options(package_options)

        default_options = getattr(conanfile, "default_options", None)
        if default_options:
            if isinstance(default_options, tuple):
                default_values = OptionsValues.loads("\n".join(default_options))
            elif isinstance(default_options, list):
                default_values = OptionsValues.from_list(default_options)
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
        # Actual requirements of this conans
        if not hasattr(conanfile, "requires"):
            return Requirements()
        else:
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


class ConanFile(object):
    """ The base class for all conans
    """

    name = None
    version = None  # Any str, can be "1.1" or whatever
    url = None  # The URL where this File is located, as github, to collaborate in package
    license = None  # The license of the PACKAGE, just a shortcut, does not replace or
                    # change the actual license of the source code
    author = None  # Main maintainer/responsible for the package, any format

    def __init__(self, output, runner, settings, conanfile_directory):
        '''
        param settings: Settings
        '''

        # User defined generators
        self.generators = self.generators if hasattr(self, "generators") else ["txt"]
        self.generators = [self.generators] if isinstance(self.generators, str) \
                                            else self.generators

        # User defined options
        self.options = create_options(self)
        self.requires = create_requirements(self)
        self.settings = create_settings(self, settings)
        self.exports = create_exports(self)

        # needed variables to pack the project
        self.cpp_info = None  # Will be initialized at processing time
        self.deps_cpp_info = DepsCppInfo()
        self.copy = None  # initialized at runtime

        # an output stream (writeln, info, warn error)
        self.output = output
        # something that can run commands, as os.sytem
        self._runner = runner

        self._conanfile_directory = conanfile_directory

    @property
    def conanfile_directory(self):
        return self._conanfile_directory

    def source(self):
        pass

    def requirements(self):
        pass

    def system_requirements(self):
        """ this method can be overriden to implement logic for system package
        managers, as apt-get

        You can define self.global_system_requirements = True, if you want the installation
        to be for all packages (not depending on settings/options/requirements)
        """

    def config(self):
        """ override this method to define custom options,
        delete non relevant ones
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
        retcode = self._runner(command, output, cwd)
        if retcode != 0:
            raise ConanException("Error %d while executing %s" % (retcode, command))

    def conan_info(self):
        """ modify the conans info, typically to narrow values
        eg.: conaninfo.package_references = []
        """

    def test(self):
        raise ConanException("You need to create a method 'test' in your test/conanfile.py")

    def __repr__(self):
        result = []
        result.append("name: %s" % self.name)
        result.append("version: %s" % self.version)
        return '\n'.join(result)
