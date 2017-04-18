from conans.model.profile import Profile
from conans.errors import ConanException
from collections import defaultdict, OrderedDict
from conans.model.env_info import EnvValues
from conans.model.options import OptionsValues
from conans.model.scope import Scopes


def profile_from_args(args, cwd, default_folder):
    """ Return a Profile object, as the result of merging a potentially existing Profile
    file and the args command-line arguments
    """
    file_profile = Profile.read_file(args.profile, cwd, default_folder)
    args_profile = _profile_parse_args(args.settings, args.options, args.env, args.scope)

    if file_profile:
        file_profile.update(args_profile)
        return file_profile
    else:
        return args_profile


def _profile_parse_args(settings, options, envs, scopes):
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

    def _get_env_values(env, package_env):
        env_values = EnvValues()
        for name, value in env:
            env_values.add(name, EnvValues.load_value(value))
        for package, data in package_env.items():
            for name, value in data:
                env_values.add(name, EnvValues.load_value(value), package)
        return env_values

    result = Profile()
    options = _get_tuples_list_from_extender_arg(options)
    result.options = OptionsValues(options)
    env, package_env = _get_simple_and_package_tuples(envs)
    env_values = _get_env_values(env, package_env)
    result.env_values = env_values
    settings, package_settings = _get_simple_and_package_tuples(settings)
    result.settings = OrderedDict(settings)
    for pkg, values in package_settings.items():
        result.package_settings[pkg] = OrderedDict(values)
    result.scopes = Scopes.from_list(scopes) if scopes else Scopes()
    return result
