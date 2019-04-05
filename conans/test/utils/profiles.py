import os

from conans.model.options import OptionsValues
from conans.model.profile import Profile
from conans.util.files import save


def create_profile(folder, name, settings=None, package_settings=None, env=None,
                   package_env=None, options=None):

    package_env = package_env or {}

    profile = Profile()
    profile.settings = settings or {}

    if package_settings:
        for pkg_name, values in package_settings.items():
            profile.update_package_settings(pkg_name, values)

    if options:
        profile.options = OptionsValues(options)

    for package_name, envs in package_env.items():
        for var_name, value in envs:
            profile.env_values.add(var_name, value, package_name)

    for var_name, value in env or {}:
        profile.env_values.add(var_name, value)

    save(os.path.join(folder, name), profile.dumps())
