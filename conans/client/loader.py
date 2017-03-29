import imp
import inspect
import os
import sys
import uuid

from conans.client.generators import _save_generator
from conans.errors import ConanException, NotFoundException
from conans.model.conan_file import ConanFile, create_exports, create_exports_sources
from conans.model.conan_generator import Generator
from conans.model.options import OptionsValues
from conans.model.ref import ConanFileReference
from conans.model.scope import Scopes
from conans.model.settings import Settings
from conans.model.values import Values
from conans.util.config_parser import ConfigParser
from conans.util.files import load
from conans.util.files import rmdir
from conans.paths import BUILD_INFO, CONANINFO
from conans.model.build_info import DepsCppInfo
from conans.model.profile import Profile
from conans.model.info import ConanInfo


def _apply_initial_deps_infos_to_conanfile(conanfile, initial_deps_infos):
    if not initial_deps_infos:
        return

    def apply_infos(infos):
        for build_dep_reference, info in infos.items():  # List of tuples (cpp_info, env_info)
            cpp_info, env_info = info
            conanfile.deps_cpp_info.update(cpp_info, build_dep_reference)
            conanfile.deps_env_info.update(env_info, build_dep_reference)

    # If there are some specific package-level deps infos apply them
    if conanfile.name and conanfile.name in initial_deps_infos.keys():
        apply_infos(initial_deps_infos[conanfile.name])

    # And also apply the global ones
    apply_infos(initial_deps_infos[None])


def _load_info_file(current_path, conanfile, output, error=False):
    info_file_path = os.path.join(current_path, BUILD_INFO)
    try:
        deps_info = DepsCppInfo.loads(load(info_file_path))
        conanfile.deps_cpp_info = deps_info
    except IOError:
        error_msg = ("%s file not found in %s\nIt is %s for this command\n"
                     "You can generate it using 'conan install -g %s'"
                     % (BUILD_INFO, current_path, "required" if error else "recommended", "txt"))
        if not error:
            output.warn(error_msg)
        else:
            raise ConanException(error_msg)
    except ConanException:
        raise ConanException("Parse error in '%s' file in %s" % (BUILD_INFO, current_path))


def _parse_module(conanfile_module, filename):
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

    return result


def _parse_file(conan_file_path):
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


def load_conanfile_class(conanfile_path, check_name_version=False):
    """ Load only the class of the ConanFile recipe, but do not instantiate the object
    It is needed for the 'conan export' command
    """
    loaded, filename = _parse_file(conanfile_path)
    try:
        result = _parse_module(loaded, filename)
        # Exports is the only object field, we need to do this, because conan export needs it
        result.exports = create_exports(result)
        result.exports_sources = create_exports_sources(result)
    except Exception as e:  # re-raise with file name
        raise ConanException("%s: %s" % (conanfile_path, str(e)))

    # check name and version were specified
    if check_name_version:
        if not hasattr(result, "name") or not result.name:
            raise ConanException("conanfile didn't specify name")
        if not hasattr(result, "version") or not result.version:
            raise ConanException("conanfile didn't specify version")

    return result


def _get_single_loader(current_path, settings, runner):
    mixed_profile = Profile()
    conan_info_path = os.path.join(current_path, CONANINFO)
    if conan_info_path and os.path.exists(conan_info_path):
        existing_info = ConanInfo.load_file(conan_info_path)
        settings.values = existing_info.full_settings
        mixed_profile.options = existing_info.full_options
        mixed_profile.scopes = existing_info.scope
        mixed_profile.env_values = existing_info.env_values

    loader = ConanFileLoader(runner,
                             settings=settings,
                             package_settings=mixed_profile.package_settings_values,
                             options=mixed_profile.options, scopes=mixed_profile.scopes,
                             env_values=mixed_profile.env_values)
    return loader


def load_conanfile_single(conanfile_path, current_path, settings, runner, output, reference=None,
                          error=False):
    loader = _get_single_loader(current_path, settings, runner)
    consumer = not reference
    conanfile = loader.load_conan(conanfile_path, output, consumer, reference)
    _load_info_file(current_path, conanfile, output, error)
    return conanfile


def load_conanfile_txt_single(conanfile_path, current_path, settings, runner, output, error=False):
    loader = _get_single_loader(current_path, settings, runner)
    conanfile = loader.load_conan_txt(conanfile_path, output)
    _load_info_file(current_path, conanfile, output, error)
    return conanfile


def install_loader(settings, profile, runner):
    settings.values = profile.settings_values

    return ConanFileLoader(runner,
                           settings=settings,
                           package_settings=profile.package_settings_values,
                           options=profile.options, scopes=profile.scopes,
                           env_values=profile.env_values)


class ConanFileLoader(object):
    def __init__(self, runner, settings, package_settings, options, scopes, env_values):
        '''
        @param settings: Settings object, to assign to ConanFile at load time
        @param options: OptionsValues, necessary so the base conanfile loads the options
                        to start propagation, and having them in order to call build()
        @param package_settings: Dict with {recipe_name: {setting_name: setting_value}}
        @param cached_env_values: EnvValues object
        '''
        self._runner = runner
        assert settings is None or isinstance(settings, Settings)
        assert options is None or isinstance(options, OptionsValues)
        assert scopes is None or isinstance(scopes, Scopes)
        # assert package_settings is None or isinstance(package_settings, dict)
        self._settings = settings
        self._user_options = options
        self._scopes = scopes

        self._package_settings = package_settings
        self._env_values = env_values
        self.initial_deps_infos = None

    def load_conan(self, conanfile_path, output, consumer=False, reference=None):
        """ loads a ConanFile object from the given file
        """
        loaded, filename = _parse_file(conanfile_path)
        try:
            result = _parse_module(loaded, filename)
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

            # Assign environment
            result._env_values.update(self._env_values)

            if consumer:
                self._user_options.descope_options(result.name)
                result.options.initialize_upstream(self._user_options)
                # If this is the consumer project, it has no name
                result.scope = self._scopes.package_scope()
            else:
                result.scope = self._scopes.package_scope(result.name)

            _apply_initial_deps_infos_to_conanfile(result, self.initial_deps_infos)
            return result
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conanfile_path, str(e)))

    def load_conan_txt(self, conan_txt_path, output):
        if not os.path.exists(conan_txt_path):
            raise NotFoundException("Conanfile not found!")

        contents = load(conan_txt_path)
        path = os.path.dirname(conan_txt_path)

        conanfile = self._parse_conan_txt(contents, path, output)
        return conanfile

    def _parse_conan_txt(self, contents, path, output):
        conanfile = ConanFile(output, self._runner, Settings(), path)
        # It is necessary to copy the settings, because the above is only a constraint of
        # conanfile settings, and a txt doesn't define settings. Necessary for generators,
        # as cmake_multi, that check build_type.
        conanfile.settings = self._settings.copy()

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
        conanfile.options.initialize_upstream(self._user_options)

        # imports method
        conanfile.imports = ConanFileTextLoader.imports_method(conanfile,
                                                               parser.import_parameters)
        conanfile.scope = self._scopes.package_scope()
        conanfile._env_values.update(self._env_values)
        return conanfile

    def load_virtual(self, references, path):
        # If user don't specify namespace in options, assume that it is
        # for the reference (keep compatibility)
        conanfile = ConanFile(None, self._runner, self._settings.copy(), path)

        # Assign environment
        conanfile._env_values.update(self._env_values)

        for ref in references:
            conanfile.requires.add(str(ref))  # Convert to string necessary
            # Allows options without package namespace in conan install commands:
            #   conan install zlib/1.2.8@lasote/stable -o shared=True
            self._user_options.scope_options(ref.name)
        conanfile.options.initialize_upstream(self._user_options)

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
