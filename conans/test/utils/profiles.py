from conans.model.profile import Profile
from conans.model.scope import Scopes
from conans.util.files import save
import os


def create_profile(folder, name, settings=None, scopes=None, package_settings=None, env=None,
                   package_env=None):

    package_env = package_env or {}

    profile = Profile()
    profile._settings = settings or {}
    if scopes:
        profile.scopes = Scopes.from_list(["%s=%s" % (key, value) for key, value in scopes.items()])

    if package_settings:
        profile._package_settings = package_settings

    for package_name, envs in package_env.items():
        for var_name, value in envs:
            profile._package_env[package_name][var_name] = value

    for var_name, value in env or {}:
        profile._env[var_name] = value

    save(os.path.join(folder, name), profile.dumps())
