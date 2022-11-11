import os

from conans.client.cache.cache import ClientCache
from conans.client.profile_loader import ProfileLoader
from conans.model.profile import Profile


class ProfilesAPI:

    def __init__(self, conan_api):
        self._cache = ClientCache(conan_api.cache_folder)

    def get_default_host(self):
        """
        :return: the path to the default "host" profile, either in the cache or as defined
            by the user in configuration
        """
        loader = ProfileLoader(self._cache)
        return loader.get_default_host()

    def get_default_build(self):
        """
        :return: the path to the default "build" profile, either in the cache or as
            defined by the user in configuration
        """
        loader = ProfileLoader(self._cache)
        return loader.get_default_build()

    def get_profiles_from_args(self, args):
        build = [self.get_default_build()] if not args.profile_build else args.profile_build
        host = [self.get_default_host()] if not args.profile_host else args.profile_host
        profile_build = self.get_profile(profiles=build, settings=args.settings_build,
                                         options=args.options_build, conf=args.conf_build)
        profile_host = self.get_profile(profiles=host, settings=args.settings_host,
                                        options=args.options_host, conf=args.conf_host)
        return profile_host, profile_build

    def get_profile(self, profiles, settings=None, options=None, conf=None, cwd=None):
        """ Computes a Profile as the result of aggregating all the user arguments, first it
        loads the "profiles", composing them in order (last profile has priority), and
        finally adding the individual settings, options (priority over the profiles)
        """
        assert isinstance(profiles, list), "Please provide a list of profiles"
        loader = ProfileLoader(self._cache)
        env = None  # TODO: Not handling environment
        profile = loader.from_cli_args(profiles, settings, options, env, conf, cwd)
        # Apply the new_config to the profiles the global one, so recipes get it too
        profile.conf.rebase_conf_definition(self._cache.new_config)
        return profile

    def get_path(self, profile, cwd=None, exists=True):
        """
        :return: the resolved path of the given profile name, that could be in the cache,
            or local, depending on the "cwd"
        """
        loader = ProfileLoader(self._cache)
        profile_path = loader.get_profile_path(profile, cwd, exists=exists)
        return profile_path

    def list(self):
        """
        List all the profiles file sin the cache
        :return: an alphabetically ordered list of profile files in the default cache location
        """
        profiles = []
        profiles_path = self._cache.profiles_path
        if os.path.exists(profiles_path):
            for current_directory, _, files in os.walk(profiles_path, followlinks=True):
                for filename in files:
                    rel_path = os.path.relpath(os.path.join(current_directory, filename),
                                               profiles_path)
                    profiles.append(rel_path)

        profiles.sort()
        return profiles

    def detect(self):
        """
        :return: an automatically detected Profile, with a "best guess" of the system settings
        """
        profile = Profile()
        from conans.client.conf.detect import detect_defaults_settings
        settings = detect_defaults_settings()
        for name, value in settings:
            profile.settings[name] = value
        # TODO: This profile is very incomplete, it doesn't have the processed_settings
        #  good enough at the moment for designing the API interface, but to improve
        return profile
