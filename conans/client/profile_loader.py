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
        self.text = text

    @property
    def _defs_block_text(self):
        """Returns the text for #includes and vars declaration"""
        ret_lines = []
        for line in self.text.splitlines():
            if not line:
                continue
            elif line.strip().startswith("["):
                return "\n".join(ret_lines)
            else:
                ret_lines.append(line)
        return "\n".join(ret_lines)

    @property
    def config_block_text(self):
        """Returns the text for pure profile"""
        if not "[" in self.text:
            return ""
        return "[" + self.text.split("[", 1)[1]

    def _apply_parent_variables(self, variables):
        # Only directly applied to vars definitions
        tmp_block_defs = self._defs_block_text
        for name, value in variables.items():
            tmp_block_defs = tmp_block_defs.replace(name, value)

        self.text = tmp_block_defs + "\n" + self.config_block_text

    def apply_variables(self, parent_vars):
        # First apply the parent variables in the inner variable declarations
        self._apply_parent_variables(parent_vars)
        # Then merge local and parent variables and apply them
        local_vars = self.local_vars
        for name, value in parent_vars.items():
            if name not in local_vars:
                local_vars[name] = value

        tmp_block_text = self.config_block_text
        for name, value in local_vars.items():
            tmp_block_text = tmp_block_text.replace("$%s" % name, value)

        self.text = self._defs_block_text + "\n" + tmp_block_text

    @property
    def includes(self):
        ret = []
        for line in self._defs_block_text.splitlines():
            if not line:
                continue
            if line.strip().startswith("include("):
                include = line.split("include(", 1)[1]
                if not include.endswith(")"):
                    raise ConanException("Invalid include statement")
                include = include[:-1]
                ret.append(include)
            else:
                return ret

        return ret

    @property
    def local_vars(self):
        vars = OrderedDict()  # Order matters, if user declares F=1 and then FOO=12, and in profile MYVAR=$FOO, it will
        # be replaced with F getting: MYVAR=1OO

        for line in self._defs_block_text.splitlines():
            if not line:
                continue
            elif line.strip().startswith("#"):
                continue
            elif line.strip().startswith("["):
                return vars
            elif line.strip().startswith("include("):
                # includes, later
                pass
            else:
                print(line)
                name, value = line.split("=", 1)
                name = name.strip()
                if " " in name:
                    raise ConanException("The names of the variables cannot contain spaces")
                value = unquote(value)
                vars[name] = value

        return vars


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
    elif profile_name.startswith("."):  # relative path name
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
        return load_profile(text, profile_path, default_folder)
    except ConanException as exc:
        import traceback
        print(traceback.format_exc())
        raise ConanException("Error reading '%s' profile: %s" % (profile_name, exc))


def load_profile(text, profile_path, default_folder):
    """ Parse and return a Profile object from a text config like representation.
        cwd is needed to be able to load the includes
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

    try:
        obj = Profile()
        cwd = os.path.dirname(os.path.abspath(profile_path)) if profile_path else None
        profile_parser = ProfileParser(text)
        inherited_vars = dict()
        for include in profile_parser.includes:
            # Recursion !!
            profile, declared_vars = read_profile(include, cwd, default_folder)
            obj.update(profile)
            inherited_vars.update(declared_vars)

        if cwd:
            inherited_vars["PROFILE_DIR"] = os.path.abspath(cwd)  # Allows PYTHONPATH=$PROFILE_DIR/pythontools

        # Replace the variables from parents
        profile_parser.apply_variables(inherited_vars)

        # Current profile before update with parents (but parent variables already applied)
        doc = ConfigParser(profile_parser.config_block_text,
                           allowed_fields=["build_requires", "settings", "env", "scopes", "options"])

        for setting in doc.settings.splitlines():
            setting = setting.strip()
            if setting and not setting.startswith("#"):
                if "=" not in setting:
                    raise ConanException("Invalid setting line '%s'" % setting)
                package_name, name, value = get_package_name_value(setting)
                if package_name:
                    obj.package_settings[package_name][name] = value
                else:
                    obj.settings[name] = value

        if doc.build_requires:
            # FIXME CHECKS OF DUPLICATED?
            for req in doc.build_requires.splitlines():
                tokens = req.split(":", 1)
                if len(tokens) == 1:
                    pattern, req_list = "*", req
                else:
                    pattern, req_list = tokens
                req_list = [ConanFileReference.loads(r.strip()) for r in req_list.split(",")]
                obj.build_requires.setdefault(pattern, []).extend(req_list)

        if doc.scopes:
            obj.scopes = Scopes.from_list(doc.scopes.splitlines())

        if doc.options:
            obj.options = OptionsValues.loads(doc.options)

        obj.env_values = EnvValues.loads(doc.env)
        return obj, profile_parser.local_vars

    except ConanException:
        raise
    except Exception as exc:
        import traceback
        print(traceback.format_exc())
        raise ConanException("Error parsing the profile text file: %s" % str(exc))
