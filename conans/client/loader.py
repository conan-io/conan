import fnmatch
import imp
import inspect
import os
import sys
import uuid

import yaml

from conans.client import settings_preprocessor
from conans.client.conf.required_version import validate_conan_version
from conans.client.loader_txt import ConanFileTextLoader
from conans.client.tools.files import chdir
from conans.errors import ConanException, NotFoundException, ConanInvalidConfiguration, \
    conanfile_exception_formatter
from conans.model.conan_file import ConanFile
from conans.model.options import Options
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.paths import DATA_YML
from conans.util.files import load


class ConanFileLoader(object):

    def __init__(self, runner,  pyreq_loader=None, requester=None):
        self._runner = runner

        self._pyreq_loader = pyreq_loader
        self._cached_conanfile_classes = {}
        self._requester = requester

    def load_basic(self, conanfile_path, graph_lock=None, display=""):
        """ loads a conanfile basic object without evaluating anything
        """
        return self.load_basic_module(conanfile_path, graph_lock, display)[0]

    def load_basic_module(self, conanfile_path, graph_lock=None, display=""):
        """ loads a conanfile basic object without evaluating anything, returns the module too
        """
        cached = self._cached_conanfile_classes.get(conanfile_path)
        if cached:
            conanfile = cached[0](self._runner, display)
            conanfile._conan_requester = self._requester
            if hasattr(conanfile, "init") and callable(conanfile.init):
                with conanfile_exception_formatter(str(conanfile), "init"):
                    conanfile.init()
            return conanfile, cached[1]

        try:
            module, conanfile = parse_conanfile(conanfile_path)

            # This is the new py_requires feature, to supersede the old python_requires
            if self._pyreq_loader:
                self._pyreq_loader.load_py_requires(conanfile, self, graph_lock)

            conanfile.recipe_folder = os.path.dirname(conanfile_path)

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

            self._cached_conanfile_classes[conanfile_path] = (conanfile, module)
            result = conanfile(self._runner, display)

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

    def load_named(self, conanfile_path, name, version, user, channel, graph_lock=None):
        """ loads the basic conanfile object and evaluates its name and version
        """
        conanfile, _ = self.load_basic_module(conanfile_path, graph_lock)

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

        if user:
            if conanfile.user and user != conanfile.user:
                raise ConanException("Package recipe with user %s!=%s"
                                     % (user, conanfile.user))
            conanfile.user = user

        if channel:
            if conanfile.channel and channel != conanfile.channel:
                raise ConanException("Package recipe with channel %s!=%s"
                                     % (channel, conanfile.channel))
            conanfile.channel = channel

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

    def load_export(self, conanfile_path, name, version, user, channel, graph_lock=None):
        """ loads the conanfile and evaluates its name, version, and enforce its existence
        """
        conanfile = self.load_named(conanfile_path, name, version, user, channel,
                                    graph_lock)
        if not conanfile.name:
            raise ConanException("conanfile didn't specify name")
        if not conanfile.version:
            raise ConanException("conanfile didn't specify version")

        ref = ConanFileReference(conanfile.name, conanfile.version, conanfile.user,
                                 conanfile.channel)
        conanfile.display_name = str(ref)
        conanfile.output.scope = conanfile.display_name
        return conanfile

    @staticmethod
    def _initialize_conanfile(conanfile, profile):
        # Prepare the settings for the loaded conanfile
        # Mixing the global settings with the specified for that name if exist
        tmp_settings = profile.processed_settings.copy()
        package_settings_values = profile.package_settings_values
        if conanfile.user is not None:
            ref_str = "%s/%s@%s/%s" % (conanfile.name, conanfile.version,
                                       conanfile.user, conanfile.channel)
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
                        # TODO: Conan 2.0 won't stop at first match
                        break
            if pkg_settings:
                tmp_settings.update_values(pkg_settings)
                # if the global settings are composed with per-package settings, need to preprocess
                settings_preprocessor.preprocess(tmp_settings)

        conanfile.initialize(tmp_settings, profile.buildenv)
        conanfile.conf = profile.conf.get_conanfile_conf(ref_str)

    def load_consumer(self, conanfile_path, profile_host, name=None, version=None, user=None,
                      channel=None, graph_lock=None, require_overrides=None):
        """ loads a conanfile.py in user space. Might have name/version or not
        """
        conanfile = self.load_named(conanfile_path, name, version, user, channel,
                                    graph_lock)

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

            if require_overrides is not None:
                for req_override in require_overrides:
                    req_override = ConanFileReference.loads(req_override)
                    conanfile.requires.override(req_override)

            return conanfile
        except ConanInvalidConfiguration:
            raise
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conanfile_path, str(e)))

    def load_conanfile(self, conanfile_path, profile, ref, graph_lock=None):
        """ load a conanfile with a full reference, name, version, user and channel are obtained
        from the reference, not evaluated. Main way to load from the cache
        """
        try:
            conanfile, _ = self.load_basic_module(conanfile_path, graph_lock, str(ref))
        except Exception as e:
            raise ConanException("%s: Cannot load recipe.\n%s" % (str(ref), str(e)))

        conanfile.name = ref.name
        # FIXME Conan 2.0, version should be a string not a Version object
        conanfile.version = ref.version
        conanfile.user = ref.user
        conanfile.channel = ref.channel

        if profile.dev_reference and profile.dev_reference == ref:
            conanfile.develop = True
        try:
            self._initialize_conanfile(conanfile, profile)
            return conanfile
        except ConanInvalidConfiguration:
            raise
        except Exception as e:  # re-raise with file name
            raise ConanException("%s: %s" % (conanfile_path, str(e)))

    def load_conanfile_txt(self, conan_txt_path, profile_host, ref=None):
        if not os.path.exists(conan_txt_path):
            raise NotFoundException("Conanfile not found!")

        contents = load(conan_txt_path)
        path, basename = os.path.split(conan_txt_path)
        display_name = "%s (%s)" % (basename, ref) if ref and ref.name else basename
        conanfile = self._parse_conan_txt(contents, path, display_name, profile_host)
        return conanfile

    def _parse_conan_txt(self, contents, path, display_name, profile):
        conanfile = ConanFile(self._runner, display_name)
        tmp_settings = profile.processed_settings.copy()
        package_settings_values = profile.package_settings_values
        if "&" in package_settings_values:
            pkg_settings = package_settings_values.get("&")
            if pkg_settings:
                tmp_settings.update_values(pkg_settings)
        tmp_settings._unconstrained = True
        conanfile.initialize(tmp_settings, profile.buildenv)
        conanfile.conf = profile.conf.get_conanfile_conf(None)

        try:
            parser = ConanFileTextLoader(contents)
        except Exception as e:
            raise ConanException("%s:\n%s" % (path, str(e)))
        for reference in parser.requirements:
            conanfile.requires(reference)
        for build_reference in parser.build_requirements:
            # TODO: Improve this interface
            conanfile.requires.build_require(build_reference)

        conanfile.generators = parser.generators

        try:
            values = Options.loads(parser.options)
            conanfile.options.update_options(values)
        except Exception:
            raise ConanException("Error while parsing [options] in conanfile\n"
                                 "Options should be specified as 'pkg:option=value'")

        # imports method
        conanfile.imports = parser.imports_method(conanfile)
        return conanfile

    def load_virtual(self, references, profile_host, is_build_require=False, require_overrides=None):
        # If user don't specify namespace in options, assume that it is
        # for the reference (keep compatibility)
        conanfile = ConanFile(self._runner, display_name="virtual")
        tmp_settings = profile_host.processed_settings.copy()
        tmp_settings._unconstrained = True
        conanfile.initialize(tmp_settings, profile_host.buildenv)
        conanfile.conf = profile_host.conf.get_conanfile_conf(None)

        if is_build_require:
            for reference in references:
                conanfile.requires.build_require(repr(reference))
        else:
            for reference in references:
                conanfile.requires(repr(reference))

        if require_overrides is not None:
            for req_override in require_overrides:
                req_override = ConanFileReference.loads(req_override)
                conanfile.requires.override(req_override)

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

    if result is None:
        raise ConanException("No subclass of ConanFile")

    return result


def parse_conanfile(conanfile_path):
    module, filename = _parse_conanfile(conanfile_path)
    try:
        conanfile = _parse_module(module, filename)
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
            sys.dont_write_bytecode = True
            loaded = imp.load_source(module_id, conan_file_path)
            sys.dont_write_bytecode = old_dont_write_bytecode

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
