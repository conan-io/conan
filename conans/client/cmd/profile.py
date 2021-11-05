import os

from conans.cli.output import ConanOutput
from conans.client.conf.detect import detect_defaults_settings
from conans.client.profile_loader import ProfileLoader
from conans.errors import ConanException
from conans.model.options import Options
from conans.model.profile import Profile
from conans.util.files import save


def _get_profile_keys(key):
    # settings.compiler.version => settings, compiler.version
    tmp = key.split(".")
    first_key = tmp[0]
    rest_key = ".".join(tmp[1:]) if len(tmp) > 1 else None
    if first_key not in ("build_requires", "settings", "options", "env", "conf"):
        raise ConanException("Invalid specified key: %s" % key)

    return first_key, rest_key


def cmd_profile_list(cache_profiles_path):
    profiles = []
    if os.path.exists(cache_profiles_path):
        for current_directory, _, files in os.walk(cache_profiles_path, followlinks=True):
            for filename in files:
                rel_path = os.path.relpath(os.path.join(current_directory, filename),
                                           cache_profiles_path)
                profiles.append(rel_path)

    if not profiles:
        ConanOutput().info("No profiles defined")
    profiles.sort()
    return profiles


def cmd_profile_create(profile_name, cache, detect=False, force=False):
    profile_loader = ProfileLoader(cache)
    profile_path = profile_loader.get_profile_path(profile_name, os.getcwd(), exists=False)
    if not force and os.path.exists(profile_path):
        raise ConanException("Profile already exists")

    profile = Profile()
    if detect:
        settings = detect_defaults_settings()
        for name, value in settings:
            profile.settings[name] = value

    contents = profile.dumps()
    save(profile_path, contents)

    output = ConanOutput()
    if detect:
        output.info("Profile created with detected settings: %s" % profile_path)
    else:
        output.info("Empty profile created: %s" % profile_path)
    return profile_path


def cmd_profile_update(profile_name, key, value, cache):
    first_key, rest_key = _get_profile_keys(key)

    profile_loader = ProfileLoader(cache)
    profile = profile_loader.load_profile(profile_name, os.getcwd())
    if first_key == "settings":
        profile.settings[rest_key] = value
    elif first_key == "options":
        tmp = Options(options_values={rest_key: value})
        profile.options.update_options(tmp)
    elif first_key == "buildenv":
        raise ConanException("Edit the profile manually to change the buildenv")
    elif first_key == "conf":
        profile.conf.update(rest_key, value)
    elif first_key == "build_requires":
        raise ConanException("Edit the profile manually to change the build_requires")
    else:
        raise ConanException("Wrong key '{}' in profile update".format(first_key))

    contents = profile.dumps()
    profile_path = profile_loader.get_profile_path(profile_name, os.getcwd())
    save(profile_path, contents)


def cmd_profile_get(profile_name, key, cache):
    first_key, rest_key = _get_profile_keys(key)
    profile_loader = ProfileLoader(cache)
    profile = profile_loader.load_profile(profile_name, os.getcwd())
    try:
        if first_key == "settings":
            return profile.settings[rest_key]
        elif first_key == "options":
            if ":" in rest_key:
                pkg, var = rest_key.split(":")
                return getattr(profile.options[pkg], var)
            else:
                return getattr(profile.options, rest_key)
        elif first_key == "env":
            package = None
            var = rest_key
            if ":" in rest_key:
                package, var = rest_key.split(":")
            return profile.env_values.data[package][var]
        elif first_key == "conf":
            return profile.conf[rest_key]
        elif first_key == "build_requires":
            raise ConanException("List the profile manually to see the build_requires")
    except KeyError:
        raise ConanException("Key not found: '%s'" % key)


def cmd_profile_delete_key(profile_name, key, cache):
    first_key, rest_key = _get_profile_keys(key)
    profile_loader = ProfileLoader(cache)
    profile = profile_loader.load_profile(profile_name, os.getcwd())
    try:
        package, name = rest_key.split(":")
    except ValueError:
        package = None
        name = rest_key

    try:
        if first_key == "settings":
            del profile.settings[rest_key]
        elif first_key == "options":
            if package is None:
                delattr(profile.options, name)
            else:
                delattr(profile.options[package], name)
        elif first_key == "env":
            profile.env_values.remove(name, package)
        elif first_key == "conf":
            del profile.conf[rest_key]
        elif first_key == "build_requires":
            raise ConanException("Edit the profile manually to delete a build_require")
    except KeyError:
        raise ConanException("Profile key '%s' doesn't exist" % key)

    contents = profile.dumps()
    profile_path = profile_loader.get_profile_path(profile_name, os.getcwd())
    save(profile_path, contents)
