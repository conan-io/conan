import os

from conans.errors import ConanException
from conans.client.profile_loader import read_profile, get_profile_path
from conans.util.files import save
from conans.model.scope import Scopes
from conans.model.env_info import EnvValues
from conans.model.options import OptionsValues


def _get_profile_keys(key):
    # settings.compiler.version => settings, compiler.version
    tmp = key.split(".")
    first_key = tmp[0]
    rest_key = ".".join(tmp[1:]) if len(tmp) > 1 else None
    if first_key not in ("build_requires", "settings", "options", "scopes", "env"):
        raise ConanException("Invalid specified key: %s" % key)

    return first_key, rest_key


def cmd_profile_update(profile_name, key, value, cache_profiles_path):
    first_key, rest_key = _get_profile_keys(key)

    profile, _ = read_profile(profile_name, os.getcwd(), cache_profiles_path)
    if first_key == "settings":
        profile.settings[rest_key] = value
    elif first_key == "options":
        tmp = OptionsValues([(rest_key, value)])
        profile.options.update(tmp)
    elif first_key == "env":
        profile.env_values.update(EnvValues.loads("%s=%s" % (rest_key, value)))
    elif first_key == "scopes":
        profile.update_scopes(Scopes.from_list(["%s=%s" % (rest_key, value)]))
    elif first_key == "build_requires":
        raise ConanException("Edit the profile manually to change the build_requires")

    contents = profile.dumps()
    profile_path = get_profile_path(profile_name, cache_profiles_path, os.getcwd())
    save(profile_path, contents)


def cmd_profile_get(profile_name, key, cache_profiles_path):
    first_key, rest_key = _get_profile_keys(key)
    profile, _ = read_profile(profile_name, os.getcwd(), cache_profiles_path)
    try:
        if first_key == "settings":
            return profile.settings[rest_key]
        elif first_key == "options":
            return dict(profile.options.as_list())[rest_key]
        elif first_key == "env":
            package = None
            var = rest_key
            if ":" in rest_key:
                package, var = rest_key.split(":")
            return profile.env_values.data[package][var]
        elif first_key == "build_requires":
            raise ConanException("List the profile manually to see the build_requires")
    except KeyError:
        raise ConanException("Key not found: '%s'" % key)


def cmd_profile_delete_key(profile_name, key, cache_profiles_path):
    first_key, rest_key = _get_profile_keys(key)
    profile, _ = read_profile(profile_name, os.getcwd(), cache_profiles_path)

    # For options, scopes, env vars
    try:
        package, name = rest_key.split(":")
    except ValueError:
        package = None
        name = rest_key

    try:
        if first_key == "settings":
            del profile.settings[rest_key]
        elif first_key == "options":
            profile.options.remove(name, package)
        elif first_key == "env":
            profile.env_values.remove(name, package)
        elif first_key == "scopes":
            profile.scopes.remove(name, package)
        elif first_key == "build_requires":
            raise ConanException("Edit the profile manually to delete a build_require")
    except KeyError:
        raise ConanException("Profile key '%s' doesn't exist" % key)

    contents = profile.dumps()
    profile_path = get_profile_path(profile_name, cache_profiles_path, os.getcwd())
    save(profile_path, contents)
