import os

from conans.model.profile import Profile
from conans.model.scope import Scopes
from conans.util.files import save


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
            profile.env_values.add(var_name, value, package_name)

    for var_name, value in env or {}:
        profile.env_values.add(var_name, value)

    save(os.path.join(folder, name), profile.dumps())
