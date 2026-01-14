import os

from conan.api.output import ConanOutput
from conan.internal.cache.concurrency_lock import ConcurrencyLock
from conan.internal.cache.home_paths import HomePaths

from conan.internal.loader import load_python_file
from conan.internal.api.profile.profile_loader import ProfileLoader
from conan.internal.errors import scoped_traceback
from conan.errors import ConanException
from conan.internal.model.profile import Profile
from conan.internal.util.files import save

DEFAULT_PROFILE_NAME = "default"


class ProfilesAPI:

    def __init__(self, conan_api, api_helpers):
        self._conan_api = conan_api
        self._api_helpers = api_helpers
        self._home_paths = HomePaths(conan_api.home_folder)
        self._lock = ConcurrencyLock(conan_api.home_folder)

    def get_default_host(self):
        """
        :return: the path to the default "host" profile, either in the cache or as defined
            by the user in configuration
        """
        default_profile = os.environ.get("CONAN_DEFAULT_PROFILE")
        if default_profile is None:
            global_conf = self._api_helpers.global_conf
            default_profile = global_conf.get("core:default_profile", default=DEFAULT_PROFILE_NAME)

        default_profile = os.path.join(self._home_paths.profiles_path, default_profile)
        if not os.path.exists(default_profile):
            msg = ("The default host profile '{}' doesn't exist.\n"
                   "You need to create a default profile (type 'conan profile detect' command)\n"
                   "or specify your own profile with '--profile:host=<myprofile>'")
            # TODO: Add detailed instructions when cli is improved
            raise ConanException(msg.format(default_profile))
        return default_profile

    def get_default_build(self):
        """
        :return: the path to the default "build" profile, either in the cache or as
            defined by the user in configuration
        """
        default_profile = os.environ.get("CONAN_DEFAULT_BUILD_PROFILE")
        if default_profile is None:
            global_conf = self._api_helpers.global_conf
            default_profile = global_conf.get("core:default_build_profile",
                                              default=DEFAULT_PROFILE_NAME)
        default_profile = os.path.join(self._home_paths.profiles_path, default_profile)
        if not os.path.exists(default_profile):
            msg = ("The default build profile '{}' doesn't exist.\n"
                   "You need to create a default profile (type 'conan profile detect' command)\n"
                   "or specify your own profile with '--profile:build=<myprofile>'")
            # TODO: Add detailed instructions when cli is improved
            raise ConanException(msg.format(default_profile))
        return default_profile

    def get_profiles_from_args(self, args):
        build_profiles = args.profile_build or [self.get_default_build()]
        host_profiles = args.profile_host or [self.get_default_host()]

        global_conf = self._api_helpers.global_conf
        global_conf.validate()  # TODO: Remove this from here
        cache_settings = self._api_helpers.settings_yml
        profile_plugin = self._load_profile_plugin()
        cwd = os.getcwd()
        profile_build = self._get_profile(build_profiles, args.settings_build, args.options_build,
                                          args.conf_build, cwd, cache_settings,
                                          profile_plugin, global_conf, context="build")
        profile_host = self._get_profile(host_profiles, args.settings_host, args.options_host, args.conf_host,
                                         cwd, cache_settings, profile_plugin, global_conf, context="host")
        return profile_host, profile_build

    def get_profile(self, profiles, settings=None, options=None, conf=None, cwd=None, context=None):
        """ Computes a Profile as the result of aggregating all the user arguments, first it
        loads the "profiles", composing them in order (last profile has priority), and
        finally adding the individual settings, options (priority over the profiles)
        """
        assert isinstance(profiles, list), "Please provide a list of profiles"
        global_conf = self._api_helpers.global_conf
        global_conf.validate()  # TODO: Remove this from here
        cache_settings = self._api_helpers.settings_yml
        profile_plugin = self._load_profile_plugin()

        profile = self._get_profile(profiles, settings, options, conf, cwd, cache_settings,
                                    profile_plugin, global_conf, context=context)
        return profile

    def _get_profile(self, profiles, settings, options, conf, cwd, cache_settings,
                     profile_plugin, global_conf, context):
        loader = ProfileLoader(self._conan_api.cache_folder)
        profile = loader.from_cli_args(profiles, settings, options, conf, cwd, context)
        if profile_plugin is not None:
            try:
                profile_plugin(profile)
            except Exception as e:
                msg = f"Error while processing 'profile.py' plugin"
                msg = scoped_traceback(msg, e, scope="/extensions/plugins")
                raise ConanException(msg)
        profile.process_settings(cache_settings)
        profile.conf.validate()
        # Apply the new_config to the profiles the global one, so recipes get it too
        profile.conf.rebase_conf_definition(global_conf)
        for k, v in sorted(profile.options._package_options.items()):
            ConanOutput().warning("Unscoped option definition is ambiguous.\n"
                                  f"Use '&:{k}={v}' to refer to the current package.\n"
                                  f"Use '*:{k}={v}' or other pattern if the intent was to apply to "
                                  f"dependencies", warn_tag="legacy")
        if profile.conf.get("tools.graph:skip_test", check_type=bool):
            ConanOutput().warning("Usage of 'tools.graph:skip_test'", warn_tag="experimental")
            if not profile.conf.get("tools.build:skip_test", check_type=bool):
                ConanOutput().warning("tools.graph:skip_test set, but tools.build:skip_test is not, "
                                      "probably you need to define it too")
        return profile

    def get_path(self, profile, cwd=None, exists=True):
        """
        :return: the resolved path of the given profile name, that could be in the cache,
            or local, depending on the "cwd"
        """
        cwd = cwd or os.getcwd()
        profiles_folder = self._home_paths.profiles_path
        profile_path = ProfileLoader.get_profile_path(profiles_folder, profile, cwd, exists=exists)
        return profile_path

    def list(self):
        """
        List all the profiles file sin the cache
        :return: an alphabetically ordered list of profile files in the default cache location
        """
        # List is to be extended (directories should not have a trailing slash)
        paths_to_ignore = ['.DS_Store']

        profiles = []
        profiles_path = self._home_paths.profiles_path
        if os.path.exists(profiles_path):
            for current_directory, _, files in os.walk(profiles_path, followlinks=True):
                files = filter(lambda file: os.path.relpath(
                    os.path.join(current_directory, file), profiles_path) not in paths_to_ignore, files)

                for filename in files:
                    rel_path = os.path.relpath(os.path.join(current_directory, filename),
                                               profiles_path)
                    profiles.append(rel_path)

        profiles.sort()
        return profiles

    @staticmethod
    def detect():
        """
        :return: an automatically detected Profile, with a "best guess" of the system settings
        """
        profile = Profile()
        from conan.internal.api.profile.detect import detect_defaults_settings
        settings = detect_defaults_settings()
        for name, value in settings:
            profile.settings[name] = value
        # TODO: This profile is very incomplete, it doesn't have the processed_settings
        #  good enough at the moment for designing the API interface, but to improve
        return profile

    def detect_and_save(self, profile_name="default", force=False, exist_ok=False):
        """
        Detect and save a profile atomically with proper locking.

        This method provides thread-safe and process-safe profile detection and saving.
        It protects against race conditions when multiple processes try to create or
        overwrite the same profile simultaneously.

        :param profile_name: Name of the profile to create (default: "default")
        :param force: If True, overwrite existing profile
        :param exist_ok: If True, do nothing if profile already exists
        :return: The detected Profile object if created, None if skipped (exist_ok=True)
        :raises ConanException: If profile already exists and neither force nor exist_ok is True
        """
        profile_pathname = self.get_path(profile_name, os.getcwd(), exists=False)

        # Use config_lock to serialize access to this profile file
        # Lock name is per-profile to allow concurrent detection of different profiles
        lock_name = f"profile_{profile_name.replace(os.sep, '_')}"

        with self._lock.config_lock(lock_name):
            # Check existence inside lock to avoid TOCTOU race
            if os.path.exists(profile_pathname):
                if exist_ok:
                    ConanOutput().info(f"Profile '{profile_name}' already exists, skipping detection")
                    return None
                if not force:
                    raise ConanException(f"Profile '{profile_pathname}' already exists")

            # Detect profile
            detected_profile = self.detect()
            contents = detected_profile.dumps()

            # Create directory if needed (inside lock)
            dir_path = os.path.dirname(profile_pathname)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

            # Write file atomically using temp file + rename pattern
            # This prevents other processes from seeing partial file contents
            # Same pattern used in remotes.py:340-341
            tmp_path = profile_pathname + ".tmp"
            save(tmp_path, contents)
            os.replace(tmp_path, profile_pathname)

            return detected_profile

    def _load_profile_plugin(self):
        profile_plugin = self._home_paths.profile_plugin_path
        if not os.path.exists(profile_plugin):
            raise ConanException("The 'profile.py' plugin file doesn't exist. If you want "
                                 "to disable it, edit its contents instead of removing it")

        mod, _ = load_python_file(profile_plugin)
        if hasattr(mod, "profile_plugin"):
            return mod.profile_plugin
