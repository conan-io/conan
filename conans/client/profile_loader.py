import os
import platform
from collections import OrderedDict, defaultdict

from jinja2 import Environment, FileSystemLoader

from conan.tools.env.environment import ProfileEnvironment
from conans.errors import ConanException, ConanV2Exception
from conans.model.conf import ConfDefinition
from conans.model.env_info import EnvValues, unquote
from conans.model.options import OptionsValues
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.util.config_parser import ConfigParser
from conans.util.files import load, mkdir
from conans.util.log import logger


class ProfileParser(object):

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
            if not line.strip() or line.strip().startswith("#"):
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


def get_profile_path(profile_name, default_folder, cwd, exists=True):
    def valid_path(_profile_path, _profile_name=None):
        if exists and not os.path.isfile(_profile_path):
            raise ConanException("Profile not found: {}".format(_profile_name or _profile_path))
        return _profile_path

    if os.path.isabs(profile_name):
        return valid_path(profile_name)

    if profile_name[:2] in ("./", ".\\") or profile_name.startswith(".."):  # local
        profile_path = os.path.abspath(os.path.join(cwd, profile_name))
        return valid_path(profile_path, profile_name)

    if not os.path.exists(default_folder):
        mkdir(default_folder)
    profile_path = os.path.join(default_folder, profile_name)
    if exists:
        if not os.path.isfile(profile_path):
            profile_path = os.path.abspath(os.path.join(cwd, profile_name))
        if not os.path.isfile(profile_path):
            raise ConanException("Profile not found: %s" % profile_name)
    return profile_path


def read_profile(profile_name, cwd, default_folder):
    """ Will look for "profile_name" in disk if profile_name is absolute path,
    in current folder if path is relative or in the default folder otherwise.
    return: a Profile object
    """
    if not profile_name:
        return None, None

    profile_path = get_profile_path(profile_name, default_folder, cwd)
    logger.debug("PROFILE LOAD: %s" % profile_path)
    text = load(profile_path)

    if profile_name.endswith(".jinja"):
        base_path = os.path.dirname(profile_path)
        context = {"platform": platform,
                   "os": os,
                   "profile_dir": base_path}
        rtemplate = Environment(loader=FileSystemLoader(base_path)).from_string(text)
        text = rtemplate.render(context)

    try:
        return _load_profile(text, profile_path, default_folder)
    except ConanV2Exception:
        raise
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
        # Iterate the includes and call recursive to get the profile and variables
        # from parent profiles
        for include in profile_parser.get_includes():
            # Recursion !!
            profile, included_vars = read_profile(include, cwd, default_folder)
            inherited_profile.compose_profile(profile)
            profile_parser.update_vars(included_vars)

        # Apply the automatic PROFILE_DIR variable
        if cwd:
            profile_parser.vars["PROFILE_DIR"] = os.path.abspath(cwd).replace('\\', '/')

        # Replace the variables from parents in the current profile
        profile_parser.apply_vars()

        # Current profile before update with parents (but parent variables already applied)
        doc = ConfigParser(profile_parser.profile_text,
                           allowed_fields=["build_requires", "tool_requires", "settings", "env",
                                           "options", "conf", "buildenv"])

        # Merge the inherited profile with the readed from current profile
        _apply_inner_profile(doc, inherited_profile)

        return inherited_profile, profile_parser.vars
    except ConanException:
        raise
    except Exception as exc:
        raise ConanException("Error parsing the profile text file: %s" % str(exc))


def _load_single_build_require(profile, line):

    tokens = line.split(":", 1)
    if len(tokens) == 1:
        pattern, req_list = "*", line
    else:
        pattern, req_list = tokens
    refs = [ConanFileReference.loads(reference.strip()) for reference in req_list.split(",")]
    profile.build_requires.setdefault(pattern, []).extend(refs)


def _apply_inner_profile(doc, base_profile):
    """

    :param doc: ConfigParser object from the current profile (excluding includes and vars,
    and with values already replaced)
    :param base_profile: Profile inherited, it's used as a base profile to modify it.
    :return: None
    """

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
            _load_single_build_require(base_profile, req)

    if doc.tool_requires:
        for req in doc.tool_requires.splitlines():
            _load_single_build_require(base_profile, req)

    if doc.options:
        base_profile.options.update(OptionsValues.loads(doc.options))

    # The env vars from the current profile (read in doc)
    # are updated with the included profiles (base_profile)
    # the current env values has priority
    current_env_values = EnvValues.loads(doc.env)
    current_env_values.update(base_profile.env_values)
    base_profile.env_values = current_env_values

    if doc.conf:
        new_prof = ConfDefinition()
        new_prof.loads(doc.conf, profile=True)
        base_profile.conf.update_conf_definition(new_prof)

    if doc.buildenv:
        buildenv = ProfileEnvironment.loads(doc.buildenv)
        base_profile.buildenv.update_profile_env(buildenv)


def profile_from_args(profiles, settings, options, env, conf, cwd, cache, build_profile=False):
    """ Return a Profile object, as the result of merging a potentially existing Profile
    file and the args command-line arguments
    """
    # Ensures a default profile creating
    default_profile = cache.default_profile
    create_profile = profiles or settings or options or env or conf or not build_profile

    if profiles is None:
        default_name = "core:default_build_profile" if build_profile else "core:default_profile"
        default_conf = cache.new_config[default_name]
        if default_conf is not None:
            default_profile_path = default_conf if os.path.isabs(default_conf) \
                else os.path.join(cache.profiles_path, default_conf)
            result, _ = read_profile(default_profile_path, os.getcwd(), cache.profiles_path)
        elif create_profile:
            result = default_profile
        else:
            result = None
    else:
        result = Profile()
        for p in profiles:
            tmp, _ = read_profile(p, cwd, cache.profiles_path)
            result.compose_profile(tmp)

    args_profile = _profile_parse_args(settings, options, env, conf)

    if result:
        result.compose_profile(args_profile)
    else:
        if create_profile:
            result = args_profile
    return result


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

    def _get_env_values(_env, _package_env):
        _env_values = EnvValues()
        for name, value in _env:
            _env_values.add(name, EnvValues.load_value(value))
        for package, data in _package_env.items():
            for name, value in data:
                _env_values.add(name, EnvValues.load_value(value), package)
        return _env_values

    options = _get_tuples_list_from_extender_arg(options)
    env, package_env = _get_simple_and_package_tuples(envs)
    env_values = _get_env_values(env, package_env)
    settings, package_settings = _get_simple_and_package_tuples(settings)

    result = Profile()
    result.options = OptionsValues(options)
    result.env_values = env_values
    result.settings = OrderedDict(settings)
    if conf:
        result.conf = ConfDefinition()
        result.conf.loads("\n".join(conf))

    for pkg, values in package_settings.items():
        result.package_settings[pkg] = OrderedDict(values)

    return result
