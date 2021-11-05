import os

from conans.client.cache.cache import ClientCache
from conans.client.conf.detect import detect_defaults_settings
from conans.client.profile_loader import ProfileLoader
from conans.errors import ConanException
from conans.model.profile import Profile
from conans.util.files import save


class ProfilesAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def get_profile(self, profiles=None, settings=None, options=None, conf=None,
                    cwd=None, build_profile=False):
        cache = ClientCache(self.conan_api.cache_folder)
        loader = ProfileLoader(cache)
        env = None  # TODO: Not handling environment
        profile = loader.from_cli_args(profiles, settings, options, env, conf, cwd, build_profile)
        return profile

    def get_path(self, profile, cwd=None):
        cache = ClientCache(self.conan_api.cache_folder)
        loader = ProfileLoader(cache)
        profile = loader.get_profile_path(profile, cwd, exists=True)
        return profile

    def list(self):
        cache = ClientCache(self.conan_api.cache_folder)
        profiles = []
        profiles_path = cache.profiles_path
        if os.path.exists(profiles_path):
            for current_directory, _, files in os.walk(profiles_path, followlinks=True):
                for filename in files:
                    rel_path = os.path.relpath(os.path.join(current_directory, filename),
                                               profiles_path)
                    profiles.append(rel_path)

        profiles.sort()
        return profiles

    def detect(self, profile_name=None, force=False):
        profile_name = profile_name or "default"
        cache = ClientCache(self.conan_api.cache_folder)
        loader = ProfileLoader(cache)
        # TODO: Improve this interface here, os.getcwd() should never be necessary here
        profile_path = loader.get_profile_path(profile_name, cwd=os.getcwd(), exists=False)


        profile = Profile()
        settings = detect_defaults_settings(profile_path)
        for name, value in settings:
            profile.settings[name] = value

        return profile
