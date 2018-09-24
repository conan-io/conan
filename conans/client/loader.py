import os
import sys
import imp
import inspect
import uuid

from conans.client.loader_txt import ConanFileTextLoader
from conans.errors import ConanException, NotFoundException
from conans.model.conan_file import ConanFile
from conans.model.options import OptionsValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.model.values import Values
from conans.util.files import load
from conans.client.output import ScopedOutput
from conans.model.profile import Profile
from conans.client.generators import registered_generators
from conans.model.conan_generator import Generator
from conans.client.tools.files import chdir


class ProcessedProfile(object):
    def __init__(self, settings=None, profile=None, create_reference=None):
        settings = settings or Settings()
        profile = profile or Profile()
        assert isinstance(settings, Settings)
        # assert package_settings is None or isinstance(package_settings, dict)
        self._settings = settings
        self._user_options = profile.options.copy()

        self._package_settings = profile.package_settings_values
        self._env_values = profile.env_values
        # Make sure the paths are normalized first, so env_values can be just a copy
        self._env_values.normalize_paths()
        self._dev_reference = create_reference


class ConanFileLoader(object):
    def __init__(self, runner, output, python_requires):
        self._runner = runner
        self._output = output
        self._python_requires = python_requires
        sys.modules["conans"].python_requires = python_requires

    def load_class(self, conanfile_path):
        loaded, filename = _parse_file(conanfile_path)
        try:
            conanfile = _parse_module(loaded, filename)
            conanfile.python_requires = self._python_requires.references
            return conanfile
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conanfile_path, str(e)))

    def load_export(self, conanfile_path, name, version, user, channel):
        conanfile = self.load_class(conanfile_path)

        # check name and version were specified
        if not conanfile.name:
            if name:
                conanfile.name = name
            else:
                raise ConanException("conanfile didn't specify name")
        elif name and name != conanfile.name:
            raise ConanException("Package recipe exported with name %s!=%s" % (name, conanfile.name))

        if not conanfile.version:
            if version:
                conanfile.version = version
            else:
                raise ConanException("conanfile didn't specify version")
        elif version and version != conanfile.version:
            raise ConanException("Package recipe exported with version %s!=%s"
                                 % (version, conanfile.version))

        conan_ref = ConanFileReference(conanfile.name, conanfile.version, user, channel)
        output = ScopedOutput(str(conan_ref), self._output)
        return conan_ref, conanfile(output, self._runner, user, channel)

    def load_basic(self, conanfile_path, output, reference=None):
        result = self.load_class(conanfile_path)
        try:
            if reference:
                result.name, result.version, user, channel = reference
            else:
                user, channel = None, None
                result.in_local_cache = False

            # Instance the conanfile
            result = result(output, self._runner, user, channel)
            return result
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conanfile_path, str(e)))

    def load_conanfile(self, conanfile_path, output, processed_profile,
                       consumer=False, reference=None, local=False):
        """ loads a ConanFile object from the given file
        """
        conanfile = self.load_basic(conanfile_path, output, reference)
        if processed_profile._dev_reference and processed_profile._dev_reference == reference:
            conanfile.develop = True
        try:
            # Prepare the settings for the loaded conanfile
            # Mixing the global settings with the specified for that name if exist
            tmp_settings = processed_profile._settings.copy()
            if processed_profile._package_settings and conanfile.name in processed_profile._package_settings:
                # Update the values, keeping old ones (confusing assign)
                values_tuple = processed_profile._package_settings[conanfile.name]
                tmp_settings.values = Values.from_list(values_tuple)

            conanfile.initialize(tmp_settings, processed_profile._env_values, local)

            if consumer:
                conanfile.develop = True
                processed_profile._user_options.descope_options(conanfile.name)
                conanfile.options.initialize_upstream(processed_profile._user_options, local=local,
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
        conanfile = ConanFile(None, self._runner, processed_profile._settings.copy())
        conanfile.initialize(processed_profile._settings.copy(), processed_profile._env_values)
        conanfile.settings = processed_profile._settings.copy_values()

        for reference in references:
            conanfile.requires.add(str(reference))  # Convert to string necessary
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


def _parse_module(conanfile_module, filename):
    """ Parses a python in-memory module, to extract the classes, mainly the main
    class defining the Recipe, but also process possible existing generators
    @param conanfile_module: the module to be processed
    @return: the main ConanFile class from the module
    """
    result = None
    for name, attr in conanfile_module.__dict__.items():
        if name[0] == "_":
            continue
        if (inspect.isclass(attr) and issubclass(attr, ConanFile) and attr != ConanFile and
                attr.__dict__["__module__"] == filename):
            if result is None:
                result = attr
            else:
                raise ConanException("More than 1 conanfile in the file")
        if (inspect.isclass(attr) and issubclass(attr, Generator) and attr != Generator and
                attr.__dict__["__module__"] == filename):
            registered_generators.add(attr.__name__, attr)

    if result is None:
        raise ConanException("No subclass of ConanFile")

    return result


def _invalid_python_requires(require):
    raise ConanException("Invalid use of python_requires(%s)" % require)


def _parse_file(conan_file_path):
    """ From a given path, obtain the in memory python import module
    """

    if not os.path.exists(conan_file_path):
        raise NotFoundException("%s not found!" % conan_file_path)

    filename = os.path.splitext(os.path.basename(conan_file_path))[0]

    try:
        current_dir = os.path.dirname(conan_file_path)
        sys.path.append(current_dir)
        old_modules = list(sys.modules.keys())
        with chdir(current_dir):
            sys.dont_write_bytecode = True
            loaded = imp.load_source(filename, conan_file_path)
            loaded.python_requires = _invalid_python_requires
            sys.dont_write_bytecode = False
        # Put all imported files under a new package name
        module_id = uuid.uuid1()
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
        sys.path.pop()

    return loaded, filename
