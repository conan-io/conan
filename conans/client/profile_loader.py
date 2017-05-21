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


class ProfileLoader(object):

    def __init__(self, profile_name, cwd, default_folder):
        self._profile_name = profile_name
        self._cwd = cwd
        self._default_folder = default_folder

    @staticmethod
    def read_conaninfo(current_path):
        profile = Profile()
        conan_info_path = os.path.join(current_path, CONANINFO)
        if os.path.exists(conan_info_path):
            existing_info = ConanInfo.load_file(conan_info_path)
            profile.settings = OrderedDict(existing_info.full_settings.as_list())
            profile.options = existing_info.full_options
            profile.scopes = existing_info.scope
            profile.env_values = existing_info.env_values
        return profile

    @staticmethod
    def _get_includes(self, text):
        ret = []
        for line in text.splitlines():
            if not line:
                continue
            if line.strip().startswith("#include "):
                ret.append(line[line.find("#include "):].strip())
                return vars
            else:
                return ret

        return ret

    @staticmethod
    def get_vars(self, text):
        vars = OrderedDict() # Order matters, if user declares F=1 and then FOO=12, and in profile MYVAR=$FOO, it will
                             # be replaced with F getting: MYVAR=1OO

        vars["PROFILE_DIR"] = os.path.abspath(self._cwd)  # Allows PYTHONPATH=$PROFILE_DIR/pythontools
        for line in text.splitlines():
            if not line:
                continue
            if line.strip().startswith("["):
                return vars
            elif line.strip().startswith("#include"):
                # includes, later
                pass
            else:
                name, value = line.split("=", 1)
                name = name.strip()
                if " " in name:
                    raise ConanException("The names of the variables cannot contain spaces")
                value = unquote(value)
                vars[name] = value

        return vars

    def read_file(self):
        """ Will look for "profile_name" in disk if profile_name is absolute path,
        in current folder if path is relative or in the default folder otherwise.
        return: a Profile object
        """
        if not self._profile_name:
            return None

        if os.path.isabs(self._profile_name):
            profile_path = self._profile_name
            folder = os.path.dirname(self._profile_name)
        elif self._profile_name.startswith("."):  # relative path name
            profile_path = os.path.abspath(os.path.join(self._cwd, self._profile_name))
            folder = os.path.dirname(profile_path)
        else:
            folder = self._default_folder
            if not os.path.exists(folder):
                mkdir(folder)
            profile_path = os.path.join(folder, self._profile_name)

        try:
            text = load(profile_path)
        except IOError:
            if os.path.exists(folder):
                profiles = [name for name in os.listdir(folder) if not os.path.isdir(name)]
            else:
                profiles = []
            current_profiles = ", ".join(profiles) or "[]"
            raise ConanException("Specified profile '%s' doesn't exist.\nExisting profiles: "
                                 "%s" % (self._profile_name, current_profiles))

        try:
            return Profile._loads(text, os.path.dirname(profile_path), self._default_folder)
        except ConanException as exc:
            raise ConanException("Error reading '%s' profile: %s" % (self._profile_name, exc))

    @staticmethod
    def _apply_variables(text, variables):
        for name, value in variables.items():
            text = text.replace_all(name, value)

        return text

    @staticmethod
    def _loads(text, cwd, default_folder):
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
            parent_profile = Profile()
            for include in ProfileLoader.get_includes(text):
                # Recursion
                loader = ProfileLoader(include, cwd, default_folder)
                tmp = loader.read_file()
                parent_profile.update(tmp)

            # Replace the variables from parents
            text = ProfileLoader._apply_variables(text, parent_profile.vars)

            # Current profile before update with parents (but parent variables already applied)
            obj = Profile()
            doc = ConfigParser(text, allowed_fields=["build_requires", "settings", "env", "scopes", "options"])

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

            # Update parent profile with current and return
            parent_profile.update(obj)
            return parent_profile
        except ConanException:
            raise
        except Exception as exc:
            raise ConanException("Error parsing the profile text file: %s" % str(exc))
