import fnmatch
import imp
import inspect
import os
import re
import sys
import types
import uuid

import yaml

from pathlib import Path

from conan.tools.cmake import cmake_layout
from conan.tools.google import bazel_layout
from conan.tools.microsoft import vs_layout
from conans.client.conf.required_version import validate_conan_version
from conans.client.loader_txt import ConanFileTextLoader
from conans.client.tools.files import chdir
from conans.errors import ConanException, NotFoundException, ConanInvalidConfiguration, \
    conanfile_exception_formatter
from conans.model.conan_file import ConanFile
from conans.model.conan_generator import Generator
from conans.model.options import OptionsValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.paths import DATA_YML
from conans.util.files import load


class ConanFileLoader(object):

    def __init__(self, runner, output, python_requires, generator_manager=None, pyreq_loader=None,
                 requester=None):
        self._runner = runner
        self._generator_manager = generator_manager
        self._output = output
        self._pyreq_loader = pyreq_loader
        self._python_requires = python_requires
        sys.modules["conans"].python_requires = python_requires
        self._cached_conanfile_classes = {}
        self._requester = requester

    def load_basic(self, conanfile_path, lock_python_requires=None, user=None, channel=None,
                   display=""):
        """ loads a conanfile basic object without evaluating anything
        """
        return self.load_basic_module(conanfile_path, lock_python_requires, user, channel,
                                      display)[0]

    def load_basic_module(self, conanfile_path, lock_python_requires=None, user=None, channel=None,
                          display=""):
        """ loads a conanfile basic object without evaluating anything, returns the module too
        """
        cached = self._cached_conanfile_classes.get(conanfile_path)
        if cached and cached[1] == lock_python_requires:
            conanfile = cached[0](self._output, self._runner, display, user, channel)
            conanfile._conan_requester = self._requester
            if hasattr(conanfile, "init") and callable(conanfile.init):
                with conanfile_exception_formatter(str(conanfile), "init"):
                    conanfile.init()
            return conanfile, cached[2]

        if lock_python_requires is not None:
            self._python_requires.locked_versions = {r.name: r for r in lock_python_requires}
        try:
            self._python_requires.valid = True
            module, conanfile = parse_conanfile(conanfile_path, self._python_requires,
                                                self._generator_manager)
            self._python_requires.valid = False

            self._python_requires.locked_versions = None

            # This is the new py_requires feature, to supersede the old python_requires
            if self._pyreq_loader:
                self._pyreq_loader.load_py_requires(conanfile, lock_python_requires, self)

            conanfile.recipe_folder = os.path.dirname(conanfile_path)
            conanfile.recipe_path = Path(conanfile.recipe_folder)

            # If the scm is inherited, create my own instance
            if hasattr(conanfile, "scm") and "scm" not in conanfile.__class__.__dict__:
                if isinstance(conanfile.scm, dict):
                    conanfile.scm = conanfile.scm.copy()

            # Load and populate dynamic fields from the data file
            conan_data = self._load_data(conanfile_path)
            conanfile.conan_data = conan_data
            if conan_data and '.conan' in conan_data:
                scm_data = conan_data['.conan'].get('scm')
                if scm_data:
                    conanfile.scm.update(scm_data)

            self._cached_conanfile_classes[conanfile_path] = (conanfile, lock_python_requires,
                                                              module)
            result = conanfile(self._output, self._runner, display, user, channel)
            result._conan_requester = self._requester
            if hasattr(result, "init") and callable(result.init):
                with conanfile_exception_formatter(str(result), "init"):
                    result.init()
            return result, module
        except ConanException as e:
            raise ConanException("Error loading conanfile at '{}': {}".format(conanfile_path, e))

    def load_generators(self, conanfile_path):
        """ Load generator classes from a module. Any non-generator classes
        will be ignored. python_requires is not processed.
        """
        """ Parses a python in-memory module and adds any generators found
            to the provided generator list
            @param conanfile_module: the module to be processed
            """
        conanfile_module, module_id = _parse_conanfile(conanfile_path)
        for name, attr in conanfile_module.__dict__.items():
            if (name.startswith("_") or not inspect.isclass(attr) or
                    attr.__dict__.get("__module__") != module_id):
                continue
            if issubclass(attr, Generator) and attr != Generator:
                self._generator_manager.add(attr.__name__, attr, custom=True)

    @staticmethod
    def _load_data(conanfile_path):
        data_path = os.path.join(os.path.dirname(conanfile_path), DATA_YML)
        if not os.path.exists(data_path):
            return None

        try:
            data = yaml.safe_load(load(data_path))
        except Exception as e:
            raise ConanException("Invalid yml format at {}: {}".format(DATA_YML, e))

        return data or {}

    def load_named(self, conanfile_path, name, version, user, channel, lock_python_requires=None):
        """ loads the basic conanfile object and evaluates its name and version
        """
        conanfile, _ = self.load_basic_module(conanfile_path, lock_python_requires, user, channel)

        # Export does a check on existing name & version
        if name:
            if conanfile.name and name != conanfile.name:
                raise ConanException("Package recipe with name %s!=%s" % (name, conanfile.name))
            conanfile.name = name

        if version:
            if conanfile.version and version != conanfile.version:
                raise ConanException("Package recipe with version %s!=%s"
                                     % (version, conanfile.version))
            conanfile.version = version

        if hasattr(conanfile, "set_name"):
            with conanfile_exception_formatter("conanfile.py", "set_name"):
                conanfile.set_name()
            if name and name != conanfile.name:
                raise ConanException("Package recipe with name %s!=%s" % (name, conanfile.name))
        if hasattr(conanfile, "set_version"):
            with conanfile_exception_formatter("conanfile.py", "set_version"):
                conanfile.set_version()
            if version and version != conanfile.version:
                raise ConanException("Package recipe with version %s!=%s"
                                     % (version, conanfile.version))

        return conanfile

    def load_export(self, conanfile_path, name, version, user, channel, lock_python_requires=None):
        """ loads the conanfile and evaluates its name, version, and enforce its existence
        """
        conanfile = self.load_named(conanfile_path, name, version, user, channel,
                                    lock_python_requires)
        if not conanfile.name:
            raise ConanException("conanfile didn't specify name")
        if not conanfile.version:
            raise ConanException("conanfile didn't specify version")

        # FIXME Conan 2.0, conanfile.version should be a string, not a version object

        ref = ConanFileReference(conanfile.name, conanfile.version, user, channel)
        conanfile.display_name = str(ref)
        conanfile.output.scope = conanfile.display_name
        return conanfile

    @staticmethod
    def _initialize_conanfile(conanfile, profile):
        # Prepare the settings for the loaded conanfile
        # Mixing the global settings with the specified for that name if exist
        tmp_settings = profile.processed_settings.copy()
        package_settings_values = profile.package_settings_values
        if conanfile._conan_user is not None:
            ref_str = "%s/%s@%s/%s" % (conanfile.name, conanfile.version,
                                       conanfile._conan_user, conanfile._conan_channel)
        else:
            ref_str = "%s/%s" % (conanfile.name, conanfile.version)
        if package_settings_values:
            # First, try to get a match directly by name (without needing *)
            # TODO: Conan 2.0: We probably want to remove this, and leave a pure fnmatch
            pkg_settings = package_settings_values.get(conanfile.name)

            if conanfile.develop and "&" in package_settings_values:
                # "&" overrides the "name" scoped settings.
                pkg_settings = package_settings_values.get("&")

            if pkg_settings is None:  # If there is not exact match by package name, do fnmatch
                for pattern, settings in package_settings_values.items():
                    if fnmatch.fnmatchcase(ref_str, pattern):
                        pkg_settings = settings
                        break
            if pkg_settings:
                tmp_settings.update_values(pkg_settings)

        conanfile.initialize(tmp_settings, profile.env_values, profile.buildenv)
        conanfile.conf = profile.conf.get_conanfile_conf(ref_str)

    def load_consumer(self, conanfile_path, profile_host, name=None, version=None, user=None,
                      channel=None, lock_python_requires=None, require_overrides=None):
        """ loads a conanfile.py in user space. Might have name/version or not
        """
        conanfile = self.load_named(conanfile_path, name, version, user, channel,
                                    lock_python_requires)

        ref = ConanFileReference(conanfile.name, conanfile.version, user, channel, validate=False)
        if str(ref):
            conanfile.display_name = "%s (%s)" % (os.path.basename(conanfile_path), str(ref))
        else:
            conanfile.display_name = os.path.basename(conanfile_path)
        conanfile.output.scope = conanfile.display_name
        conanfile.in_local_cache = False
        try:
            conanfile.develop = True
            self._initialize_conanfile(conanfile, profile_host)

            # The consumer specific
            profile_host.user_options.descope_options(conanfile.name)
            conanfile.options.initialize_upstream(profile_host.user_options,
                                                  name=conanfile.name)
            profile_host.user_options.clear_unscoped_options()

            if require_overrides is not None:
                for req_override in require_overrides:
                    req_override = ConanFileReference.loads(req_override)
                    conanfile.requires.override(req_override)

            return conanfile
        except ConanInvalidConfiguration:
            raise
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conanfile_path, str(e)))

    def load_conanfile(self, conanfile_path, profile, ref, lock_python_requires=None):
        """ load a conanfile with a full reference, name, version, user and channel are obtained
        from the reference, not evaluated. Main way to load from the cache
        """
        try:
            conanfile, _ = self.load_basic_module(conanfile_path, lock_python_requires,
                                                  ref.user, ref.channel, str(ref))
        except Exception as e:
            raise ConanException("%s: Cannot load recipe.\n%s" % (str(ref), str(e)))

        conanfile.name = ref.name
        # FIXME Conan 2.0, version should be a string not a Version object
        conanfile.version = ref.version

        if profile.dev_reference and profile.dev_reference == ref:
            conanfile.develop = True
        try:
            self._initialize_conanfile(conanfile, profile)
            return conanfile
        except ConanInvalidConfiguration:
            raise
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conanfile_path, str(e)))

    def load_conanfile_txt(self, conan_txt_path, profile_host, ref=None, require_overrides=None):
        if not os.path.exists(conan_txt_path):
            raise NotFoundException("Conanfile not found!")

        contents = load(conan_txt_path)
        path, basename = os.path.split(conan_txt_path)
        display_name = "%s (%s)" % (basename, ref) if ref and ref.name else basename
        conanfile = self._parse_conan_txt(contents, path, display_name, profile_host)

        if require_overrides is not None:
            for req_override in require_overrides:
                req_override = ConanFileReference.loads(req_override)
                conanfile.requires.override(req_override)

        return conanfile

    def _parse_conan_txt(self, contents, path, display_name, profile):
        conanfile = ConanFile(self._output, self._runner, display_name)
        tmp_settings = profile.processed_settings.copy()
        package_settings_values = profile.package_settings_values
        if "&" in package_settings_values:
            pkg_settings = package_settings_values.get("&")
            if pkg_settings:
                tmp_settings.update_values(pkg_settings)
        conanfile.initialize(Settings(), profile.env_values, profile.buildenv)
        conanfile.conf = profile.conf.get_conanfile_conf(None)
        # It is necessary to copy the settings, because the above is only a constraint of
        # conanfile settings, and a txt doesn't define settings. Necessary for generators,
        # as cmake_multi, that check build_type.
        conanfile.settings = tmp_settings.copy_values()

        try:
            parser = ConanFileTextLoader(contents)
        except Exception as e:
            raise ConanException("%s:\n%s" % (path, str(e)))
        for reference in parser.requirements:
            ref = ConanFileReference.loads(reference)  # Raise if invalid
            conanfile.requires.add_ref(ref)
        for build_reference in parser.build_requirements:
            ConanFileReference.loads(build_reference)
            if not hasattr(conanfile, "build_requires"):
                conanfile.build_requires = []
            conanfile.build_requires.append(build_reference)
        if parser.layout:
            layout_method = {"cmake_layout": cmake_layout,
                             "vs_layout": vs_layout,
                             "bazel_layout": bazel_layout}.get(parser.layout)
            if not layout_method:
                raise ConanException("Unknown predefined layout '{}' declared in "
                                     "conanfile.txt".format(parser.layout))

            def layout(self):
                layout_method(self)

            conanfile.layout = types.MethodType(layout, conanfile)

        conanfile.generators = parser.generators
        try:
            options = OptionsValues.loads(parser.options)
        except Exception:
            raise ConanException("Error while parsing [options] in conanfile\n"
                                 "Options should be specified as 'pkg:option=value'")
        conanfile.options.values = options
        conanfile.options.initialize_upstream(profile.user_options)

        # imports method
        conanfile.imports = parser.imports_method(conanfile)
        return conanfile

    def load_virtual(self, references, profile_host, scope_options=True,
                     build_requires_options=None, is_build_require=False, require_overrides=None):
        # If user don't specify namespace in options, assume that it is
        # for the reference (keep compatibility)
        conanfile = ConanFile(self._output, self._runner, display_name="virtual")
        conanfile.initialize(profile_host.processed_settings.copy(),
                             profile_host.env_values, profile_host.buildenv)
        conanfile.conf = profile_host.conf.get_conanfile_conf(None)
        conanfile.settings = profile_host.processed_settings.copy_values()

        if is_build_require:
            conanfile.build_requires = [str(r) for r in references]
        else:
            for reference in references:
                conanfile.requires.add_ref(reference)

        if require_overrides is not None:
            for req_override in require_overrides:
                req_override = ConanFileReference.loads(req_override)
                conanfile.requires.override(req_override)

        # Allows options without package namespace in conan install commands:
        #   conan install zlib/1.2.8@lasote/stable -o shared=True
        if scope_options:
            assert len(references) == 1
            profile_host.user_options.scope_options(references[0].name)
        if build_requires_options:
            conanfile.options.initialize_upstream(build_requires_options)
        else:
            conanfile.options.initialize_upstream(profile_host.user_options)

        conanfile.generators = []  # remove the default txt generator
        return conanfile


def _parse_module(conanfile_module, module_id, generator_manager):
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
            generator_manager.add(attr.__name__, attr, custom=True)

    if result is None:
        raise ConanException("No subclass of ConanFile")

    return result


def parse_conanfile(conanfile_path, python_requires, generator_manager):
    with python_requires.capture_requires() as py_requires:
        module, filename = _parse_conanfile(conanfile_path)
        try:
            conanfile = _parse_module(module, filename, generator_manager)

            # Check for duplicates
            # TODO: move it into PythonRequires
            py_reqs = {}
            for it in py_requires:
                if it.ref.name in py_reqs:
                    dupes = [str(it.ref), str(py_reqs[it.ref.name].ref)]
                    raise ConanException("Same python_requires with different versions not allowed"
                                         " for a conanfile. Found '{}'".format("', '".join(dupes)))
                py_reqs[it.ref.name] = it

            # Make them available to the conanfile itself
            if py_reqs:
                conanfile.python_requires = py_reqs
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
            old_dont_write_bytecode = sys.dont_write_bytecode
            try:
                sys.dont_write_bytecode = True
                # FIXME: imp is deprecated in favour of implib
                loaded = imp.load_source(module_id, conan_file_path)
                sys.dont_write_bytecode = old_dont_write_bytecode
            except ImportError:
                version_txt = _get_required_conan_version_without_loading(conan_file_path)
                if version_txt:
                    validate_conan_version(version_txt)
                raise

            required_conan_version = getattr(loaded, "required_conan_version", None)
            if required_conan_version:
                validate_conan_version(required_conan_version)

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
    except ConanException:
        raise
    except Exception:
        import traceback
        trace = traceback.format_exc().split('\n')
        raise ConanException("Unable to load conanfile in %s\n%s" % (conan_file_path,
                                                                     '\n'.join(trace[3:])))
    finally:
        sys.path.pop(0)

    return loaded, module_id


def _get_required_conan_version_without_loading(conan_file_path):
    # First, try to detect the required_conan_version in "text" mode
    # https://github.com/conan-io/conan/issues/11239
    contents = load(conan_file_path)

    txt_version = None

    try:
        found = re.search(r"required_conan_version\s*=\s*(.*)", contents)
        if found:
            txt_version = found.group(1).replace('"', "")
    except:
        pass

    return txt_version
