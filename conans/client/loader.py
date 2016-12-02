from conans.errors import ConanException, NotFoundException
from conans.model.conan_file import ConanFile, create_exports
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
from conans.model.values import Values


class ConanFileLoader(object):
    def __init__(self, runner, settings, package_settings, options, scopes, env, package_env):
        '''
        @param settings: Settings object, to assign to ConanFile at load time
        @param options: OptionsValues, necessary so the base conanfile loads the options
                        to start propagation, and having them in order to call build()
        @param package_settings: Dict with {recipe_name: {setting_name: setting_value}}
        @param env: list of tuples for environment vars: [(var, value), (var2, value2)...]
        @param package_env: package dict of list of tuples: {"name": [(var, v1), (var2, v2)...]}
        '''
        self._runner = runner
        assert settings is None or isinstance(settings, Settings)
        assert options is None or isinstance(options, OptionsValues)
        assert scopes is None or isinstance(scopes, Scopes)
        assert env is None or isinstance(env, list)
        assert package_env is None or isinstance(package_env, dict)
        # assert package_settings is None or isinstance(package_settings, dict)
        self._settings = settings
        self._options = options
        self._scopes = scopes
        self._package_settings = package_settings
        self._env = env or []
        self._package_env = package_env or {}

    def _parse_module(self, conanfile_module, consumer, filename):
        """ Parses a python in-memory module, to extract the classes, mainly the main
        class defining the Recipe, but also process possible existing generators
        @param conanfile_module: the module to be processed
        @param consumer: if this is a root node in the hierarchy, the consumer project
        @return: the main ConanFile class from the module
        """
        result = None
        for name, attr in conanfile_module.__dict__.items():
            if "_" in name:
                continue
            if (inspect.isclass(attr) and issubclass(attr, ConanFile) and attr != ConanFile and
                    attr.__dict__["__module__"] == filename):
                if result is None:
                    result = attr
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

    def _parse_file(self, conan_file_path):
        """ From a given path, obtain the in memory python import module
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

        return loaded, filename

    def load_class(self, conanfile_path):
        """ Load only the class of the ConanFile recipe, but do not instantiate the object
        It is needed for the 'conan export' command
        """
        loaded, filename = self._parse_file(conanfile_path)
        try:
            result = self._parse_module(loaded, False, filename)
            # Exports is the only object field, we need to do this, because conan export needs it
            result.exports = create_exports(result)
            return result
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conanfile_path, str(e)))

    def load_conan(self, conanfile_path, output, consumer=False, reference=None):
        """ loads a ConanFile object from the given file
        """
        loaded, filename = self._parse_file(conanfile_path)
        try:
            result = self._parse_module(loaded, consumer, filename)

            # Prepare the settings for the loaded conanfile
            # Mixing the global settings with the specified for that name if exist
            tmp_settings = self._settings.copy()
            if self._package_settings and result.name in self._package_settings:
                # Update the values, keeping old ones (confusing assign)
                values_tuple = self._package_settings[result.name]
                tmp_settings.values = Values.from_list(values_tuple)

            user, channel = (reference.user, reference.channel) if reference else (None, None)

            # Instance the conanfile
            result = result(output, self._runner, tmp_settings,
                            os.path.dirname(conanfile_path), user, channel)

            # Prepare the env variables mixing global env vars with the
            # package ones if name match
            tmp_env = []
            # Copy only the global variables not present in package level vars
            for var_name, value in self._env:
                if result.name in self._package_env:
                    if var_name not in self._package_env[result.name]:
                        tmp_env.append((var_name, value))
                else:
                    tmp_env.append((var_name, value))
            tmp_env.extend(self._package_env.get(result.name, []))
            result.env = tmp_env

            if consumer:
                result.options.initialize_upstream(self._options, result.name)
                # If this is the consumer project, it has no name
                result.scope = self._scopes.package_scope()
            else:
                result.scope = self._scopes.package_scope(result.name)
            return result
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conanfile_path, str(e)))

    def load_conan_txt(self, conan_txt_path, output):
        if not os.path.exists(conan_txt_path):
            raise NotFoundException("Conanfile not found!")

        contents = load(conan_txt_path)
        path = os.path.dirname(conan_txt_path)

        conanfile = self.parse_conan_txt(contents, path, output)
        return conanfile

    def parse_conan_txt(self, contents, path, output):
        conanfile = ConanFile(output, self._runner, self._settings.copy(), path)

        try:
            parser = ConanFileTextLoader(contents)
        except Exception as e:
            raise ConanException("%s:\n%s" % (path, str(e)))
        for requirement_text in parser.requirements:
            ConanFileReference.loads(requirement_text)  # Raise if invalid
            conanfile.requires.add(requirement_text)

        conanfile.generators = parser.generators

        options = OptionsValues.loads(parser.options)
        conanfile.options.values = options
        conanfile.options.initialize_upstream(self._options, conanfile.name)

        # imports method
        conanfile.imports = ConanFileTextLoader.imports_method(conanfile,
                                                               parser.import_parameters)
        conanfile.scope = self._scopes.package_scope()
        return conanfile

    def load_virtual(self, reference, path):
        fixed_options = []
        # If user don't specify namespace in options, assume that it is
        # for the reference (keep compatibility)
        for option_name, option_value in self._options.as_list():
            if ":" not in option_name:
                tmp = ("%s:%s" % (reference.name, option_name), option_value)
            else:
                tmp = (option_name, option_value)
            fixed_options.append(tmp)
        options = OptionsValues.from_list(fixed_options)

        conanfile = ConanFile(None, self._runner, self._settings.copy(), path)

        conanfile.requires.add(str(reference))  # Convert to string necessary
        # conanfile.options.values = options
        conanfile.options.initialize_upstream(options)

        conanfile.generators = []
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
