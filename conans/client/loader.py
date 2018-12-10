import imp
import inspect
import os
import sys
import uuid

from conans.client.generators import registered_generators
from conans.client.loader_txt import ConanFileTextLoader
from conans.client.output import ScopedOutput
from conans.client.tools.files import chdir
from conans.errors import ConanException, NotFoundException
from conans.model.conan_file import ConanFile
from conans.model.conan_generator import Generator
from conans.model.options import OptionsValues
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.model.values import Values
from conans.util.files import load
from contextlib import contextmanager


class ProcessedProfile(object):
    def __init__(self, profile=None, create_reference=None):
        if profile is None:  # FIXME: Only for testing interface
            profile = Profile()
            profile.processed_settings = Settings()
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

    @contextmanager
    def lock_versions(self, refs):
        if refs:
            self._python_requires._locked_versions = {r.name: r for r in refs}
        yield
        self._python_requires._locked_versions = None

    def load_class(self, conanfile_path):
        _, conanfile = parse_conanfile(conanfile_path, self._python_requires)
        return conanfile

    def load_name_version(self, conanfile_path, name, version):
        conanfile = self.load_class(conanfile_path)
        # Do not inherit the name from python-requires
        if "name" in conanfile.__dict__:
            if name and name != conanfile.name:
                raise ConanException("Package recipe exported with name %s!=%s"
                                     % (name, conanfile.name))
            else:
                name = conanfile.name
        elif not name:
            raise ConanException("conanfile didn't specify name")

        if "version" in conanfile.__dict__:
            if version and version != conanfile.version:
                raise ConanException("Package recipe exported with version %s!=%s"
                                     % (version, conanfile.version))
            else:
                version = conanfile.version
        elif not version:
            raise ConanException("conanfile didn't specify version")
        return name, version

    def load_export(self, conanfile_path, ref):
        # We need to silent range_resolver output of python_requires of this load_class
        conanfile = self.load_class(conanfile_path)
        conanfile.name = ref.name
        conanfile.version = ref.version
        output = ScopedOutput(str(ref), self._output)
        return conanfile(output, self._runner, ref.user, ref.channel)

    def load_basic(self, conanfile_path, output, reference=None):
        result = self.load_class(conanfile_path)
        try:
            if reference:
                result.name, result.version, user, channel, _ = reference
            else:
                user, channel = None, None
                result.in_local_cache = False

            # Instance the conanfile
            result = result(output, self._runner, user, channel)
            return result
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conanfile_path, str(e)))

    def load_conanfile(self, conanfile_path, output, processed_profile,
                       consumer=False, reference=None):
        """ loads a ConanFile object from the given file
        """
        conanfile = self.load_basic(conanfile_path, output, reference)
        if processed_profile._dev_reference and processed_profile._dev_reference == reference:
            conanfile.develop = True
        try:
            # Prepare the settings for the loaded conanfile
            # Mixing the global settings with the specified for that name if exist
            tmp_settings = processed_profile._settings.copy()
            if (processed_profile._package_settings and
                    conanfile.name in processed_profile._package_settings):
                # Update the values, keeping old ones (confusing assign)
                values_tuple = processed_profile._package_settings[conanfile.name]
                tmp_settings.values = Values.from_list(values_tuple)

            conanfile.initialize(tmp_settings, processed_profile._env_values)

            if consumer:
                conanfile.develop = True
                processed_profile._user_options.descope_options(conanfile.name)
                conanfile.options.initialize_upstream(processed_profile._user_options,
                                                      name=conanfile.name)
                processed_profile._user_options.clear_unscoped_options()

            return conanfile
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conanfile_path, str(e)))

    def load_conanfile_txt(self, conan_txt_path, output, processed_profile):
        if not os.path.exists(conan_txt_path):
            raise NotFoundException("Conanfile not found!")

        contents = load(conan_txt_path)
        path = os.path.dirname(conan_txt_path)

        conanfile = self._parse_conan_txt(contents, path, output, processed_profile)
        return conanfile

    def _parse_conan_txt(self, contents, path, output, processed_profile):
        conanfile = ConanFile(output, self._runner)
        conanfile.initialize(Settings(), processed_profile._env_values)
        # It is necessary to copy the settings, because the above is only a constraint of
        # conanfile settings, and a txt doesn't define settings. Necessary for generators,
        # as cmake_multi, that check build_type.
        conanfile.settings = processed_profile._settings.copy_values()

        try:
            parser = ConanFileTextLoader(contents)
        except Exception as e:
            raise ConanException("%s:\n%s" % (path, str(e)))
        for requirement_text in parser.requirements:
            ConanFileReference.loads(requirement_text)  # Raise if invalid
            conanfile.requires.add(requirement_text)
        for build_requirement_text in parser.build_requirements:
            ConanFileReference.loads(build_requirement_text)
            if not hasattr(conanfile, "build_requires"):
                conanfile.build_requires = []
            conanfile.build_requires.append(build_requirement_text)

        conanfile.generators = parser.generators

        options = OptionsValues.loads(parser.options)
        conanfile.options.values = options
        conanfile.options.initialize_upstream(processed_profile._user_options)

        # imports method
        conanfile.imports = parser.imports_method(conanfile)
        conanfile._conan_env_values.update(processed_profile._env_values)
        return conanfile

    def load_virtual(self, references, processed_profile, scope_options=True,
                     build_requires_options=None):
        # If user don't specify namespace in options, assume that it is
        # for the reference (keep compatibility)
        conanfile = ConanFile(None, self._runner)
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
            registered_generators.add(attr.__name__, attr)

    if result is None:
        raise ConanException("No subclass of ConanFile")

    return result


def _invalid_python_requires(require):
    raise ConanException("Invalid use of python_requires(%s)" % require)


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
            loaded.python_requires = _invalid_python_requires
            sys.dont_write_bytecode = False

        # These lines are necessary, otherwise local conanfile imports with same name
        # collide, but no error, and overwrite other packages imports!!
        added_modules = set(sys.modules).difference(old_modules)
        for added in added_modules:
            module = sys.modules[added]
            if module:
                try:
                    folder = os.path.dirname(module.__file__)
                except AttributeError:  # some module doesn't have __file__
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
