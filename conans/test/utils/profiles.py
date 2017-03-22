import os

from conans.model.profile import Profile
from conans.model.scope import Scopes
from conans.util.files import save
from conans.model.options import OptionsValues


def create_profile(folder, name, settings=None, scopes=None, package_settings=None, env=None,
                   package_env=None, options=None):

    package_env = package_env or {}

    profile = Profile()
    profile.settings = settings or {}
    if scopes:
        profile.scopes = Scopes.from_list(["%s=%s" % (key, value) for key, value in scopes.items()])

    if package_settings:
        profile.package_settings = package_settings

    if options:
        profile.options = OptionsValues(options)

    for package_name, envs in package_env.items():
        for var_name, value in envs:
            profile.env_values.add(var_name, value, package_name)

    for var_name, value in env or {}:
        profile.env_values.add(var_name, value)

    save(os.path.join(folder, name), profile.dumps())
