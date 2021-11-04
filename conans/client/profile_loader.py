import os
import platform
from collections import OrderedDict, defaultdict

from jinja2 import Environment, FileSystemLoader

from conan.tools.env.environment import ProfileEnvironment
from conans.errors import ConanException
from conans.model.conf import ConfDefinition
from conans.model.env_info import unquote
from conans.model.options import Options
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.paths import DEFAULT_PROFILE_NAME
from conans.util.config_parser import ConfigParser
from conans.util.files import load, mkdir


class ProfileLoader:
    def __init__(self, cache):
        self._cache = cache

    def from_cli_args(self, profiles, settings, options, env, conf, cwd, build_profile=False):
        """ Return a Profile object, as the result of merging a potentially existing Profile
        file and the args command-line arguments
        """
        cache = self._cache
        if profiles is None:
            if build_profile:
                default_profile = cache.new_config[
                                      "core:default_build_profile"] or DEFAULT_PROFILE_NAME
            else:
                default_profile = os.environ.get("CONAN_DEFAULT_PROFILE")
                if default_profile is None:
                    default_profile = cache.new_config[
                                          "core:default_profile"] or DEFAULT_PROFILE_NAME

            default_profile = os.path.join(cache.profiles_path, default_profile)
            if not os.path.exists(default_profile):
                msg = ("The default profile file doesn't exist:\n"
                       "{}\n"
                       "You need to create a default profile or specify your own profile")
                # TODO: Add detailed instructions when cli is improved
                raise ConanException(msg.format(default_profile))
            result = self.load_profile(default_profile, cwd)
        else:
            result = Profile()
            for p in profiles:
                tmp = self.load_profile(p, cwd)
                result.compose_profile(tmp)

        args_profile = _profile_parse_args(settings, options, env, conf)
        result.compose_profile(args_profile)
        # Only after everything has been aggregated, try to complete missing settings
        result.process_settings(self._cache)
        return result

    def load_profile(self, profile_name, cwd=None):
        cwd = cwd or os.getcwd()
        profile, _ = self._load_profile(profile_name, cwd)
        return profile

    def _load_profile(self, profile_name, cwd):
        """ Will look for "profile_name" in disk if profile_name is absolute path,
        in current folder if path is relative or in the default folder otherwise.
        return: a Profile object
        """

        profile_path = self.get_profile_path(profile_name, cwd)
        text = load(profile_path)

        if profile_name.endswith(".jinja"):
            base_path = os.path.dirname(profile_path)
            context = {"platform": platform,
                       "os": os,
                       "profile_dir": base_path}
            rtemplate = Environment(loader=FileSystemLoader(base_path)).from_string(text)
            text = rtemplate.render(context)

        try:
            return self._recurse_load_profile(text, profile_path)
        except ConanException as exc:
            raise ConanException("Error reading '%s' profile: %s" % (profile_name, exc))

    def _recurse_load_profile(self, text, profile_path):
        """ Parse and return a Profile object from a text config like representation.
            cwd is needed to be able to load the includes
        """
        try:
            inherited_profile = Profile()
            cwd = os.path.dirname(os.path.abspath(profile_path)) if profile_path else None
            profile_parser = _ProfileParser(text)
            # Iterate the includes and call recursive to get the profile and variables
            # from parent profiles
            for include in profile_parser.get_includes():
                # Recursion !!
                profile, included_vars = self._load_profile(include, cwd)
                inherited_profile.compose_profile(profile)
                profile_parser.update_vars(included_vars)

            # Apply the automatic PROFILE_DIR variable
            if cwd:
                profile_parser.vars["PROFILE_DIR"] = os.path.abspath(cwd).replace('\\', '/')

            # Replace the variables from parents in the current profile
            profile_parser.apply_vars()

            # Current profile before update with parents (but parent variables already applied)
            inherited_profile = _ProfileValueParser.get_profile(profile_parser.profile_text,
                                                                inherited_profile)
            return inherited_profile, profile_parser.vars
        except ConanException:
            raise
        except Exception as exc:
            raise ConanException("Error parsing the profile text file: %s" % str(exc))

    def get_profile_path(self, profile_name, cwd, exists=True):

        def valid_path(_profile_path, _profile_name=None):
            if exists and not os.path.isfile(_profile_path):
                raise ConanException("Profile not found: {}".format(_profile_name or _profile_path))
            return _profile_path

        if os.path.isabs(profile_name):
            return valid_path(profile_name)

        if profile_name[:2] in ("./", ".\\") or profile_name.startswith(".."):  # local
            profile_path = os.path.abspath(os.path.join(cwd, profile_name))
            return valid_path(profile_path, profile_name)

        default_folder = self._cache.profiles_path
        if not os.path.exists(default_folder):
            mkdir(default_folder)
        profile_path = os.path.join(default_folder, profile_name)
        if exists:
            if not os.path.isfile(profile_path):
                profile_path = os.path.abspath(os.path.join(cwd, profile_name))
            if not os.path.isfile(profile_path):
                raise ConanException("Profile not found: %s" % profile_name)
        return profile_path


class _ProfileParser(object):

    def __init__(self, text):
        """ divides the text in 3 items:
        - self.vars: Dictionary with variable=value declarations
        - self.includes: List of other profiles to include
        - self.profile_text: the remaining, containing settings, options, env, etc
        """
        self.vars = OrderedDict()  # Order matters, if user declares F=1 and then FOO=12,
        # and in profile MYVAR=$FOO, it will
        self.includes = []
        self.profile_text = ""

        for counter, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("["):
                self.profile_text = "\n".join(text.splitlines()[counter:])
                break
            elif line.startswith("include("):
                include = line.split("include(", 1)[1]
                if not include.endswith(")"):
                    raise ConanException("Invalid include statement")
                include = include[:-1]
                self.includes.append(include)
            else:
                try:
                    name, value = line.split("=", 1)
                except ValueError:
                    raise ConanException("Error while parsing line %i: '%s'" % (counter, line))
                name = name.strip()
                if " " in name:
                    raise ConanException("The names of the variables cannot contain spaces")
                value = unquote(value)
                self.vars[name] = value

    def apply_vars(self):
        self._apply_in_vars()
        self._apply_in_profile_text()

    def get_includes(self):
        # Replace over includes seems insane and it is not documented. I am leaving it now
        # afraid of breaking, but should be removed Conan 2.0
        for include in self.includes:
            for repl_key, repl_value in self.vars.items():
                include = include.replace("$%s" % repl_key, repl_value)
            yield include

    def update_vars(self, included_vars):
        """ update the variables dict with new ones from included profiles,
        but keeping (higher priority) existing values"""
        included_vars.update(self.vars)
        self.vars = included_vars

    def _apply_in_vars(self):
        tmp_vars = OrderedDict()
        for key, value in self.vars.items():
            for repl_key, repl_value in self.vars.items():
                key = key.replace("$%s" % repl_key, repl_value)
                value = value.replace("$%s" % repl_key, repl_value)
            tmp_vars[key] = value
        self.vars = tmp_vars

    def _apply_in_profile_text(self):
        for k, v in self.vars.items():
            self.profile_text = self.profile_text.replace("$%s" % k, v)


class _ProfileValueParser(object):
    """ parses a "pure" or "effective" profile, with no includes, no variables,
    as the one in the lockfiles, or once these things have been processed by ProfileParser
    """
    @staticmethod
    def get_profile(profile_text, base_profile=None):
        doc = ConfigParser(profile_text, allowed_fields=["build_requires", "settings", "env",
                                                         "options", "conf", "buildenv"])

        # Parse doc sections into Conan model, Settings, Options, etc
        settings, package_settings = _ProfileValueParser._parse_settings(doc)
        options = Options.loads(doc.options) if doc.options else None
        build_requires = _ProfileValueParser._parse_build_requires(doc)

        if doc.conf:
            conf = ConfDefinition()
            conf.loads(doc.conf, profile=True)
        else:
            conf = None
        buildenv = ProfileEnvironment.loads(doc.buildenv) if doc.buildenv else None

        # Create or update the profile
        base_profile = base_profile or Profile()
        base_profile.settings.update(settings)
        for pkg_name, values_dict in package_settings.items():
            base_profile.package_settings[pkg_name].update(values_dict)
        for pattern, refs in build_requires.items():
            base_profile.build_requires.setdefault(pattern, []).extend(refs)
        if options is not None:
            base_profile.options.update_options(options)

        if conf is not None:
            base_profile.conf.update_conf_definition(conf)
        if buildenv is not None:
            base_profile.buildenv.update_profile_env(buildenv)
        return base_profile

    @staticmethod
    def _parse_build_requires(doc):
        result = OrderedDict()
        if doc.build_requires:
            # FIXME CHECKS OF DUPLICATED?
            for br_line in doc.build_requires.splitlines():
                tokens = br_line.split(":", 1)
                if len(tokens) == 1:
                    pattern, req_list = "*", br_line
                else:
                    pattern, req_list = tokens
                refs = [ConanFileReference.loads(r.strip()) for r in req_list.split(",")]
                result.setdefault(pattern, []).extend(refs)
        return result

    @staticmethod
    def _parse_settings(doc):
        def get_package_name_value(item):
            """Parse items like package:name=value or name=value"""
            packagename = None
            if ":" in item:
                tmp = item.split(":", 1)
                packagename, item = tmp

            result_name, result_value = item.split("=", 1)
            result_name = result_name.strip()
            result_value = unquote(result_value)
            return packagename, result_name, result_value

        package_settings = OrderedDict()
        settings = OrderedDict()
        for setting in doc.settings.splitlines():
            setting = setting.strip()
            if not setting or setting.startswith("#"):
                continue
            if "=" not in setting:
                raise ConanException("Invalid setting line '%s'" % setting)
            package_name, name, value = get_package_name_value(setting)
            if package_name:
                package_settings.setdefault(package_name, OrderedDict())[name] = value
            else:
                settings[name] = value
        return settings, package_settings


def _profile_parse_args(settings, options, envs, conf):
    """ return a Profile object result of parsing raw data
    """
    def _get_tuples_list_from_extender_arg(items):
        if not items:
            return []
        # Validate the pairs
        for item in items:
            chunks = item.split("=", 1)
            if len(chunks) != 2:
                raise ConanException("Invalid input '%s', use 'name=value'" % item)
        return [(item[0], item[1]) for item in [item.split("=", 1) for item in items]]

    def _get_simple_and_package_tuples(items):
        """Parse items like "thing:item=value or item2=value2 and returns a tuple list for
        the simple items (name, value) and a dict for the package items
        {package: [(item, value)...)], ...}
        """
        simple_items = []
        package_items = defaultdict(list)
        tuples = _get_tuples_list_from_extender_arg(items)
        for name, value in tuples:
            if ":" in name:  # Scoped items
                tmp = name.split(":", 1)
                ref_name = tmp[0]
                name = tmp[1]
                package_items[ref_name].append((name, value))
            else:
                simple_items.append((name, value))
        return simple_items, package_items

    settings, package_settings = _get_simple_and_package_tuples(settings)

    result = Profile()
    result.options = Options.loads("\n".join(options or []))
    result.settings = OrderedDict(settings)
    if conf:
        result.conf = ConfDefinition()
        result.conf.loads("\n".join(conf))

    for pkg, values in package_settings.items():
        result.package_settings[pkg] = OrderedDict(values)

    return result
