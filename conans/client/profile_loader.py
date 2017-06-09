import os
from collections import OrderedDict

from conans.errors import ConanException
from conans.model.env_info import EnvValues, unquote
from conans.model.info import ConanInfo
from conans.model.options import OptionsValues
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.model.scope import Scopes
from conans.paths import CONANINFO
from conans.util.config_parser import ConfigParser
from conans.util.files import load, mkdir


class ProfileParser(object):

    def __init__(self, text):
        self.vars = OrderedDict() # Order matters, if user declares F=1 and then FOO=12, and in profile MYVAR=$FOO, it will
        self.includes = []
        self.profile_text = ""

        for counter, line in enumerate(text.splitlines()):
            if not line or line.strip().startswith("#"):
                continue
            elif line.strip().startswith("["):
                self.profile_text = "\n".join(text.splitlines()[counter:])
                break
            elif line.strip().startswith("include("):
                include = line.split("include(", 1)[1]
                if not include.endswith(")"):
                    raise ConanException("Invalid include statement")
                include = include[:-1]
                self.includes.append(include)
            else:
                name, value = line.split("=", 1)
                name = name.strip()
                if " " in name:
                    raise ConanException("The names of the variables cannot contain spaces")
                value = unquote(value)
                self.vars[name] = value

    def apply_vars(self, repl_vars):
        self.vars = self._apply_in_vars(repl_vars)
        self.includes = self._apply_in_includes(repl_vars)
        self.profile_text = self._apply_in_profile_text(repl_vars)

    def _apply_in_vars(self, repl_vars):
        tmp_vars = OrderedDict()
        for key, value in self.vars.items():
            for repl_key, repl_value in repl_vars.items():
                key = key.replace("$%s" % repl_key, repl_value)
                value = value.replace("$%s" % repl_key, repl_value)
            tmp_vars[key] = value
        return tmp_vars

    def _apply_in_includes(self, repl_vars):
        tmp_includes = []
        for include in self.includes:
            for repl_key, repl_value in repl_vars.items():
                include = include.replace("$%s" % repl_key, repl_value)
            tmp_includes.append(include)
        return tmp_includes

    def _apply_in_profile_text(self, repl_vars):
        tmp_text = self.profile_text
        for repl_key, repl_value in repl_vars.items():
            tmp_text = tmp_text.replace("$%s" % repl_key, repl_value)
        return tmp_text

def read_conaninfo_profile(current_path):
    profile = Profile()
    conan_info_path = os.path.join(current_path, CONANINFO)
    if os.path.exists(conan_info_path):
        existing_info = ConanInfo.load_file(conan_info_path)
        profile.settings = OrderedDict(existing_info.full_settings.as_list())
        profile.options = existing_info.full_options
        profile.scopes = existing_info.scope
        profile.env_values = existing_info.env_values
    return profile


def read_profile(profile_name, cwd, default_folder):
    """ Will look for "profile_name" in disk if profile_name is absolute path,
    in current folder if path is relative or in the default folder otherwise.
    return: a Profile object
    """
    if not profile_name:
        return None, None

    if os.path.isabs(profile_name):
        profile_path = profile_name
        folder = os.path.dirname(profile_name)
    elif cwd and os.path.exists(os.path.join(cwd, profile_name)):  # relative path name
        profile_path = os.path.abspath(os.path.join(cwd, profile_name))
        folder = os.path.dirname(profile_path)
    else:
        if not os.path.exists(default_folder):
            mkdir(default_folder)
        profile_path = os.path.join(default_folder, profile_name)
        folder = default_folder

    try:
        text = load(profile_path)
    except IOError:
        if os.path.exists(folder):
            profiles = [name for name in os.listdir(folder) if not os.path.isdir(name)]
        else:
            profiles = []
        current_profiles = ", ".join(profiles) or "[]"
        raise ConanException("Specified profile '%s' doesn't exist.\nExisting profiles: "
                             "%s" % (profile_name, current_profiles))

    try:
        return _load_profile(text, profile_path, default_folder)
    except ConanException as exc:
        raise ConanException("Error reading '%s' profile: %s" % (profile_name, exc))


def _load_profile(text, profile_path, default_folder):
    """ Parse and return a Profile object from a text config like representation.
        cwd is needed to be able to load the includes
    """

    try:
        inherited_profile = Profile()
        cwd = os.path.dirname(os.path.abspath(profile_path)) if profile_path else None
        profile_parser = ProfileParser(text)
        inherited_vars = profile_parser.vars
        # Iterate the includes and call recursive to get the profile and variables from parent profiles
        for include in profile_parser.includes:
            # Recursion !!
            profile, declared_vars = read_profile(include, cwd, default_folder)
            inherited_profile.update(profile)
            inherited_vars.update(declared_vars)

        # Apply the automatic PROFILE_DIR variable
        if cwd:
            inherited_vars["PROFILE_DIR"] = os.path.abspath(cwd)  # Allows PYTHONPATH=$PROFILE_DIR/pythontools

        # Replace the variables from parents in the current profile
        profile_parser.apply_vars(inherited_vars)

        # Current profile before update with parents (but parent variables already applied)
        doc = ConfigParser(profile_parser.profile_text,
                           allowed_fields=["build_requires", "settings", "env", "scopes", "options"])

        # Merge the inherited profile with the readed from current profile
        _apply_inner_profile(doc, inherited_profile)

        # Return the intherited vars to apply them in the parent profile if exists
        inherited_vars.update(profile_parser.vars)
        return inherited_profile, inherited_vars

    except ConanException:
        raise
    except Exception as exc:
        raise ConanException("Error parsing the profile text file: %s" % str(exc))


def _apply_inner_profile(doc, base_profile):
    """

    :param doc: ConfigParser object from the current profile (excluding includes and vars, and with values already replaced)
    :param base_profile: Profile inherited, it's used as a base profile to modify it.
    :return: None
    """

    def get_package_name_value(item):
        """Parse items like package:name=value or name=value"""
        package_name = None
        if ":" in item:
            tmp = item.split(":", 1)
            package_name, item = tmp

        name, value = item.split("=", 1)
        name = name.strip()
        value = unquote(value)
        return package_name, name, value

    for setting in doc.settings.splitlines():
        setting = setting.strip()
        if setting and not setting.startswith("#"):
            if "=" not in setting:
                raise ConanException("Invalid setting line '%s'" % setting)
            package_name, name, value = get_package_name_value(setting)
            if package_name:
                base_profile.package_settings[package_name][name] = value
            else:
                base_profile.settings[name] = value

    if doc.build_requires:
        # FIXME CHECKS OF DUPLICATED?
        for req in doc.build_requires.splitlines():
            tokens = req.split(":", 1)
            if len(tokens) == 1:
                pattern, req_list = "*", req
            else:
                pattern, req_list = tokens
            req_list = [ConanFileReference.loads(r.strip()) for r in req_list.split(",")]
            base_profile.build_requires.setdefault(pattern, []).extend(req_list)

    if doc.scopes:
        base_profile.update_scopes(Scopes.from_list(doc.scopes.splitlines()))

    if doc.options:
        base_profile.options.update(OptionsValues.loads(doc.options))

    base_profile.env_values.update(EnvValues.loads(doc.env))
