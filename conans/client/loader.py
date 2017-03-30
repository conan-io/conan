import os

from conans.errors import ConanException, NotFoundException
from conans.model.conan_file import ConanFile
from conans.model.options import OptionsValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.model.values import Values
from conans.util.files import load
from conans.paths import BUILD_INFO
from conans.model.build_info import DepsCppInfo
from conans.model.profile import Profile
from conans.client.loader_parse import ConanFileTextLoader, load_conanfile_class


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


def load_consumer_conanfile(conanfile_path, current_path, settings, runner, output, reference=None,
                            error=False):
    profile = Profile.read_conaninfo(current_path)
    loader = ConanFileLoader(runner, settings, profile)
    if conanfile_path.endswith(".py"):
        consumer = not reference
        conanfile = loader.load_conan(conanfile_path, output, consumer, reference)
    else:
        conanfile = loader.load_conan_txt(conanfile_path, output)
    _load_info_file(current_path, conanfile, output, error)
    return conanfile


class ConanFileLoader(object):
    def __init__(self, runner, settings, profile):
        '''
        @param settings: Settings object, to assign to ConanFile at load time
        @param options: OptionsValues, necessary so the base conanfile loads the options
                        to start propagation, and having them in order to call build()
        @param package_settings: Dict with {recipe_name: {setting_name: setting_value}}
        @param cached_env_values: EnvValues object
        '''
        self._runner = runner
        settings.values = profile.settings_values
        assert settings is None or isinstance(settings, Settings)
        # assert package_settings is None or isinstance(package_settings, dict)
        self._settings = settings
        self._user_options = profile.options
        self._scopes = profile.scopes

        self._package_settings = profile.package_settings_values
        self._env_values = profile.env_values
        self.initial_deps_infos = None

    def load_conan(self, conanfile_path, output, consumer=False, reference=None):
        """ loads a ConanFile object from the given file
        """
        result = load_conanfile_class(conanfile_path)
        try:
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
            self._user_options.scope_options(ref.name)  # FIXME: This only scope the 1st require
        conanfile.options.initialize_upstream(self._user_options)

        conanfile.generators = []  # remove the default txt generator
        conanfile.scope = self._scopes.package_scope()

        return conanfile
