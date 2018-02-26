import os


from conans.client.loader_parse import ConanFileTextLoader, load_conanfile_class
from conans.errors import ConanException, NotFoundException
from conans.model.conan_file import ConanFile
from conans.model.options import OptionsValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.model.values import Values
from conans.util.files import load


class ConanFileLoader(object):
    def __init__(self, runner, settings, profile):
        """
        @param settings: Settings object, to assign to ConanFile at load time
        @param options: OptionsValues, necessary so the base conanfile loads the options
                        to start propagation, and having them in order to call build()
        @param package_settings: Dict with {recipe_name: {setting_name: setting_value}}
        @param cached_env_values: EnvValues object
        """
        self._runner = runner

        assert isinstance(settings, Settings)
        # assert package_settings is None or isinstance(package_settings, dict)
        self._settings = settings
        self._user_options = profile.options.copy()

        self._package_settings = profile.package_settings_values
        self._env_values = profile.env_values
        self.dev_reference = None

    def load_conan(self, conanfile_path, output, consumer=False, reference=None, local=False):
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

            if reference:
                result.name = reference.name
                result.version = reference.version
                user, channel = reference.user, reference.channel
            else:
                user, channel = None, None

            # Instance the conanfile
            result = result(output, self._runner, tmp_settings, user, channel, local)

            # Assign environment
            result._env_values.update(self._env_values)

            if consumer:
                self._user_options.descope_options(result.name)
                result.options.initialize_upstream(self._user_options)
                self._user_options.clear_unscoped_options()
            else:
                result.in_local_cache = True

            if consumer or (self.dev_reference and self.dev_reference == reference):
                result.develop = True

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
        conanfile = ConanFile(output, self._runner, Settings())
        # It is necessary to copy the settings, because the above is only a constraint of
        # conanfile settings, and a txt doesn't define settings. Necessary for generators,
        # as cmake_multi, that check build_type.
        conanfile.settings = self._settings.copy_values()

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
        conanfile.options.initialize_upstream(self._user_options)

        # imports method
        conanfile.imports = parser.imports_method(conanfile)
        conanfile._env_values.update(self._env_values)
        return conanfile

    def load_virtual(self, references, scope_options=True,
                     build_requires_options=None):
        # If user don't specify namespace in options, assume that it is
        # for the reference (keep compatibility)
        conanfile = ConanFile(None, self._runner, self._settings.copy())
        conanfile.settings = self._settings.copy_values()
        # Assign environment
        conanfile._env_values.update(self._env_values)

        for reference in references:
            conanfile.requires.add(str(reference))  # Convert to string necessary
        # Allows options without package namespace in conan install commands:
        #   conan install zlib/1.2.8@lasote/stable -o shared=True
        if scope_options:
            assert len(references) == 1
            self._user_options.scope_options(references[0].name)
        if build_requires_options:
            conanfile.options.initialize_upstream(build_requires_options)
        else:
            conanfile.options.initialize_upstream(self._user_options)

        conanfile.generators = []  # remove the default txt generator

        return conanfile
