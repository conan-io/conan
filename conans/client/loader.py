import imp
import inspect
import os
import sys
import uuid

from conans.client.generators import registered_generators
from conans.client.loader_txt import ConanFileTextLoader
from conans.client.tools.files import chdir
from conans.errors import ConanException, NotFoundException
from conans.model.conan_file import ConanFile
from conans.model.conan_generator import Generator
from conans.model.options import OptionsValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.model.values import Values
from conans.util.files import load


class ProcessedProfile(object):
    def __init__(self, profile, create_reference=None):
        self._settings = profile.processed_settings
        self._user_options = profile.options.copy()

        self._package_settings = profile.package_settings_values
        self._env_values = profile.env_values
        # Make sure the paths are normalized first, so env_values can be just a copy
        self._dev_reference = create_reference


class ConanFileLoader(object):
    def __init__(self, runner, output, python_requires):
        self._runner = runner
        self._output = output
        self._python_requires = python_requires
        sys.modules["conans"].python_requires = python_requires
        self.cached_conanfiles = {}

    def invalidate_caches(self):
        self.cached_conanfiles = {}
        self._python_requires.invalidate_caches()

    def load_class(self, conanfile_path):
        try:
            return self.cached_conanfiles[conanfile_path]
        except KeyError:
            self._python_requires.valid = True
            _, conanfile = parse_conanfile(conanfile_path, self._python_requires)
            self._python_requires.valid = False
            self.cached_conanfiles[conanfile_path] = conanfile
        return conanfile

    def load_export(self, conanfile_path, name, version, user, channel):
        conanfile = self.load_class(conanfile_path)
        # Export does a check on existing name & version
        if "name" in conanfile.__dict__:
            if name and name != conanfile.name:
                raise ConanException("Package recipe exported with name %s!=%s"
                                     % (name, conanfile.name))
        elif not name:
            raise ConanException("conanfile didn't specify name")
        else:
            conanfile.name = name

        if "version" in conanfile.__dict__:
            if version and version != conanfile.version:
                raise ConanException("Package recipe exported with version %s!=%s"
                                     % (version, conanfile.version))
        elif not version:
            raise ConanException("conanfile didn't specify version")
        else:
            conanfile.version = version
        ref = ConanFileReference(conanfile.name, conanfile.version, user, channel)
        return conanfile(self._output, self._runner, str(ref), user, channel)

    @staticmethod
    def _initialize_conanfile(conanfile, processed_profile):
        # Prepare the settings for the loaded conanfile
        # Mixing the global settings with the specified for that name if exist
        tmp_settings = processed_profile._settings.copy()
        if (processed_profile._package_settings and
                conanfile.name in processed_profile._package_settings):
            # Update the values, keeping old ones (confusing assign)
            values_tuple = processed_profile._package_settings[conanfile.name]
            tmp_settings.values = Values.from_list(values_tuple)

        conanfile.initialize(tmp_settings, processed_profile._env_values)

    def load_consumer(self, conanfile_path, processed_profile, name=None, version=None, user=None,
                      channel=None, test=None):

        conanfile_class = self.load_class(conanfile_path)
        if name and conanfile_class.name and name != conanfile_class.name:
            raise ConanException("Package recipe name %s!=%s" % (name, conanfile_class.name))
        if version and conanfile_class.version and version != conanfile_class.version:
            raise ConanException("Package recipe version %s!=%s"
                                 % (version, conanfile_class.version))
        conanfile_class.name = name or conanfile_class.name
        conanfile_class.version = version or conanfile_class.version
        if test:
            display_name = "%s (test package)" % test
        else:
            ref = ConanFileReference(conanfile_class.name, conanfile_class.version, user, channel,
                                     validate=False)
            if ref.name or ref.version or ref.user or ref.channel:
                display_name = "%s (%s)" % (os.path.basename(conanfile_path), ref)
            else:
                display_name = os.path.basename(conanfile_path)
        conanfile = conanfile_class(self._output, self._runner, display_name, user, channel)
        conanfile.in_local_cache = False
        try:
            self._initialize_conanfile(conanfile, processed_profile)

            # The consumer specific
            conanfile.develop = True
            processed_profile._user_options.descope_options(conanfile.name)
            conanfile.options.initialize_upstream(processed_profile._user_options,
                                                  name=conanfile.name)
            processed_profile._user_options.clear_unscoped_options()

            return conanfile
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conanfile_path, str(e)))

    def load_conanfile(self, conanfile_path, processed_profile, ref):
        conanfile_class = self.load_class(conanfile_path)
        conanfile_class.name = ref.name
        conanfile_class.version = ref.version
        conanfile = conanfile_class(self._output, self._runner, str(ref), ref.user, ref.channel)
        if processed_profile._dev_reference and processed_profile._dev_reference == ref:
            conanfile.develop = True
        try:
            self._initialize_conanfile(conanfile, processed_profile)
            return conanfile
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conanfile_path, str(e)))

    def load_conanfile_txt(self, conan_txt_path, processed_profile, ref=None):
        if not os.path.exists(conan_txt_path):
            raise NotFoundException("Conanfile not found!")

        contents = load(conan_txt_path)
        path, basename = os.path.split(conan_txt_path)
        display_name = "%s (%s)" % (basename, ref) if ref and ref.name else basename
        conanfile = self._parse_conan_txt(contents, path, display_name, processed_profile)
        return conanfile

    def _parse_conan_txt(self, contents, path, display_name, processed_profile):
        conanfile = ConanFile(self._output, self._runner, display_name)
        conanfile.initialize(Settings(), processed_profile._env_values)
        # It is necessary to copy the settings, because the above is only a constraint of
        # conanfile settings, and a txt doesn't define settings. Necessary for generators,
        # as cmake_multi, that check build_type.
        conanfile.settings = processed_profile._settings.copy_values()

        try:
            parser = ConanFileTextLoader(contents)
        except Exception as e:
            raise ConanException("%s:\n%s" % (path, str(e)))
        for reference in parser.requirements:
            ConanFileReference.loads(reference)  # Raise if invalid
            conanfile.requires.add(reference)
        for build_reference in parser.build_requirements:
            ConanFileReference.loads(build_reference)
            if not hasattr(conanfile, "build_requires"):
                conanfile.build_requires = []
            conanfile.build_requires.append(build_reference)

        conanfile.generators = parser.generators

        options = OptionsValues.loads(parser.options)
        conanfile.options.values = options
        conanfile.options.initialize_upstream(processed_profile._user_options)

        # imports method
        conanfile.imports = parser.imports_method(conanfile)
        return conanfile

    def load_virtual(self, references, processed_profile, scope_options=True,
                     build_requires_options=None):
        # If user don't specify namespace in options, assume that it is
        # for the reference (keep compatibility)
        conanfile = ConanFile(self._output, self._runner, display_name="virtual")
        conanfile.initialize(processed_profile._settings.copy(), processed_profile._env_values)
        conanfile.settings = processed_profile._settings.copy_values()

        for reference in references:
            conanfile.requires.add(reference.full_repr())  # Convert to string necessary
        # Allows options without package namespace in conan install commands:
        #   conan install zlib/1.2.8@lasote/stable -o shared=True
        if scope_options:
            assert len(references) == 1
            processed_profile._user_options.scope_options(references[0].name)
        if build_requires_options:
            conanfile.options.initialize_upstream(build_requires_options)
        else:
            conanfile.options.initialize_upstream(processed_profile._user_options)

        conanfile.generators = []  # remove the default txt generator
        return conanfile


def _parse_module(conanfile_module, module_id):
    """ Parses a python in-memory module, to extract the classes, mainly the main
    class defining the Recipe, but also process possible existing generators
    @param conanfile_module: the module to be processed
    @return: the main ConanFile class from the module
    """
    result = None
    for name, attr in conanfile_module.__dict__.items():
        if (name.startswith("_") or not inspect.isclass(attr) or
                attr.__dict__.get("__module__") != module_id):
            continue

        if issubclass(attr, ConanFile) and attr != ConanFile:
            if result is None:
                result = attr
            else:
                raise ConanException("More than 1 conanfile in the file")
        elif issubclass(attr, Generator) and attr != Generator:
            registered_generators.add(attr.__name__, attr, custom=True)

    if result is None:
        raise ConanException("No subclass of ConanFile")

    return result


def parse_conanfile(conanfile_path, python_requires):
    with python_requires.capture_requires() as py_requires:
        module, filename = _parse_conanfile(conanfile_path)
        try:
            conanfile = _parse_module(module, filename)
            conanfile.python_requires = py_requires
            return module, conanfile
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conanfile_path, str(e)))


def _parse_conanfile(conan_file_path):
    """ From a given path, obtain the in memory python import module
    """

    if not os.path.exists(conan_file_path):
        raise NotFoundException("%s not found!" % conan_file_path)

    module_id = str(uuid.uuid1())
    current_dir = os.path.dirname(conan_file_path)
    sys.path.insert(0, current_dir)
    try:
        old_modules = list(sys.modules.keys())
        with chdir(current_dir):
            sys.dont_write_bytecode = True
            loaded = imp.load_source(module_id, conan_file_path)
            sys.dont_write_bytecode = False

        # These lines are necessary, otherwise local conanfile imports with same name
        # collide, but no error, and overwrite other packages imports!!
        added_modules = set(sys.modules).difference(old_modules)
        for added in added_modules:
            module = sys.modules[added]
            if module:
                try:
                    try:
                        # Most modules will have __file__ != None
                        folder = os.path.dirname(module.__file__)
                    except (AttributeError, TypeError):
                        # But __file__ might not exist or equal None
                        # Like some builtins and Namespace packages py3
                        folder = module.__path__._path[0]
                except AttributeError:  # In case the module.__path__ doesn't exist
                    pass
                else:
                    if folder.startswith(current_dir):
                        module = sys.modules.pop(added)
                        sys.modules["%s.%s" % (module_id, added)] = module
    except Exception:
        import traceback
        trace = traceback.format_exc().split('\n')
        raise ConanException("Unable to load conanfile in %s\n%s" % (conan_file_path,
                                                                     '\n'.join(trace[3:])))
    finally:
        sys.path.pop(0)

    return loaded, module_id
