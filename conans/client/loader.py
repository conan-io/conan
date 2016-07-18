from conans.errors import ConanException, NotFoundException
from conans.model.conan_file import ConanFile
from conans.util.files import rmdir
import inspect
import uuid
import imp
import os
from conans.util.files import load
from conans.util.config_parser import ConfigParser
from conans.model.options import OptionsValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
import sys
from conans.model.conan_generator import Generator
from conans.client.generators import _save_generator
from conans.model.scope import Scopes
from conans.client.output import ScopedOutput


class ConanFileLoader(object):
    def __init__(self, runner, settings, options, scopes):
        '''
        param settings: Settings object, to assign to ConanFile at load time
        param options: OptionsValues, necessary so the base conanfile loads the options
                        to start propagation, and having them in order to call build()
        '''
        self._runner = runner
        assert isinstance(settings, Settings)
        assert isinstance(options, OptionsValues)
        assert isinstance(scopes, Scopes)
        self._settings = settings
        self._options = options
        self._scopes = scopes

    def _create_check_conan(self, conan_file, consumer, conan_file_path, output, filename):
        """ Check the integrity of a given conanfile
        """
        result = None
        for name, attr in conan_file.__dict__.items():
            if "_" in name:
                continue
            if (inspect.isclass(attr) and issubclass(attr, ConanFile) and attr != ConanFile and
                    attr.__dict__["__module__"] == filename):
                if result is None:
                    # Actual instantiation of ConanFile object
                    result = attr(output, self._runner,
                                  self._settings.copy(), os.path.dirname(conan_file_path))
                else:
                    raise ConanException("More than 1 conanfile in the file")
            if (inspect.isclass(attr) and issubclass(attr, Generator) and attr != Generator and
                    attr.__dict__["__module__"] == filename):
                    _save_generator(attr.__name__, attr)

        if result is None:
            raise ConanException("No subclass of ConanFile")

        # check name and version were specified
        if not consumer:
            if not hasattr(result, "name") or not result.name:
                raise ConanException("conanfile didn't specify name")
            if not hasattr(result, "version") or not result.version:
                raise ConanException("conanfile didn't specify version")

        return result

    def load_conan(self, conan_file_path, output, consumer=False):
        """ loads a ConanFile object from the given file
        """
        # Check if precompiled exist, delete it
        if os.path.exists(conan_file_path + "c"):
            os.unlink(conan_file_path + "c")

        # Python 3
        pycache = os.path.join(os.path.dirname(conan_file_path), "__pycache__")
        if os.path.exists(pycache):
            rmdir(pycache)

        if not os.path.exists(conan_file_path):
            raise NotFoundException("%s not found!" % conan_file_path)

        filename = os.path.splitext(os.path.basename(conan_file_path))[0]

        try:
            current_dir = os.path.dirname(conan_file_path)
            sys.path.append(current_dir)
            old_modules = list(sys.modules.keys())
            loaded = imp.load_source(filename, conan_file_path)
            # Put all imported files under a new package name
            module_id = uuid.uuid1()
            added_modules = set(sys.modules).difference(old_modules)
            for added in added_modules:
                module = sys.modules[added]
                if module:
                    folder = os.path.dirname(module.__file__)
                    if folder.startswith(current_dir):
                        module = sys.modules.pop(added)
                        sys.modules["%s.%s" % (module_id, added)] = module
        except Exception:
            import traceback
            trace = traceback.format_exc().split('\n')
            raise ConanException("Unable to load conanfile in %s\n%s" % (conan_file_path,
                                                                         '\n'.join(trace[3:])))
        finally:
            sys.path.pop()

        try:
            result = self._create_check_conan(loaded, consumer, conan_file_path, output, filename)
            if consumer:
                result.options.initialize_upstream(self._options)
                # If this is the consumer project, it has no name
                result.scope = self._scopes.package_scope()
            else:
                result.scope = self._scopes.package_scope(result.name)
            return result
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conan_file_path, str(e)))

    def load_conan_txt(self, conan_requirements_path, output):

        if not os.path.exists(conan_requirements_path):
            raise NotFoundException("Conanfile not found!")

        conanfile = ConanFile(output, self._runner, self._settings.copy(),
                              os.path.dirname(conan_requirements_path))

        try:
            parser = ConanFileTextLoader(load(conan_requirements_path))
        except Exception as e:
            raise ConanException("%s:\n%s" % (conan_requirements_path, str(e)))
        for requirement_text in parser.requirements:
            ConanFileReference.loads(requirement_text)  # Raise if invalid
            conanfile.requires.add(requirement_text)

        conanfile.generators = parser.generators

        options = OptionsValues.loads(parser.options)
        conanfile.options.values = options
        conanfile.options.initialize_upstream(self._options)

        # imports method
        conanfile.imports = ConanFileTextLoader.imports_method(conanfile,
                                                               parser.import_parameters)
        conanfile.scope = self._scopes.package_scope()
        return conanfile

    def load_virtual(self, reference):
        fixed_options = []
        # If user don't specify namespace in options, assume that it's for the reference (keep compatibility)
        for option_name, option_value in self._options.as_list():
            if ":" not in option_name:
                tmp = ("%s:%s" % (reference.name, option_name), option_value)
            else:
                tmp = (option_name, option_value)
            fixed_options.append(tmp)
        options = OptionsValues.from_list(fixed_options)

        conanfile = ConanFile(None, self._runner, self._settings.copy(), None)

        conanfile.requires.add(str(reference))  # Convert to string necessary
        # conanfile.options.values = options
        conanfile.options.initialize_upstream(options)

        conanfile.generators = ["txt"]
        conanfile.scope = self._scopes.package_scope()

        return conanfile


class ConanFileTextLoader(object):
    """Parse a plain requirements file"""

    def __init__(self, input_text):
        # Prefer composition over inheritance, the __getattr__ was breaking things
        self._config_parser = ConfigParser(input_text,  ["requires", "generators", "options",
                                                         "imports"], parse_lines=True)

    @property
    def requirements(self):
        """returns a list of requires
        EX:  "OpenCV/2.4.10@phil/stable"
        """
        return [r.strip() for r in self._config_parser.requires.splitlines()]

    @property
    def options(self):
        return self._config_parser.options

    @property
    def import_parameters(self):
        ret = []
        local_install_text = self._config_parser.imports
        for local_install_line in local_install_text.splitlines():
            invalid_line_msg = "Invalid imports line: %s" \
                               "\nEX: OpenCV/lib, * -> ./lib" % local_install_line
            try:
                if local_install_line.startswith("/") or local_install_line.startswith(".."):
                    raise ConanException("Import's paths can't begin with '/' or '..'")
                pair = local_install_line.split("->")
                source = pair[0].strip().split(',', 1)
                dest = pair[1].strip()
                src, pattern = source[0].strip(), source[1].strip()
                ret.append((pattern, dest, src))
            except ConanException as excp:
                raise ConanException("%s\n%s" % (invalid_line_msg, excp.message))
            except:
                raise ConanException(invalid_line_msg)
        return ret

    @property
    def generators(self):
        return self._config_parser.generators.splitlines()

    @staticmethod
    def imports_method(conan_file, parameters):
        def imports():
            for import_params in parameters:
                conan_file.copy(*import_params)
        return imports
