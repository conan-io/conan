import ast
import asttokens
import operator
import os
from contextlib import contextmanager

from conans import tools  # @UnusedImport KEEP THIS! Needed for pyinstaller to copy to exe.
from conans.client.tools.env import pythonpath
from conans.errors import ConanException
from conans.model.build_info import DepsCppInfo
from conans.model.env_info import DepsEnvInfo, EnvValues
from conans.model.options import Options, PackageOptions, OptionsValues
from conans.model.requires import Requirements
from conans.model.user_info import DepsUserInfo
from conans.paths import RUN_LOG_NAME
from conans.tools import environment_append, no_op
from conans.client.output import Color
from conans.client.tools.oss import os_info
from conans.util.files import load, save

# Simple tag function to mark values that should be expanded during recipe export.
def conan_expand(value):
    return value

# Formats the expanded values.
def format_expanded_value(value, indentation):
    import pprint
    lines = pprint.pformat(value).splitlines()
    if isinstance(value, dict) or isinstance(value, list) or isinstance(value, tuple):
        indentation += 1
    formated = ('\n' + ' '*indentation).join(lines)
    return formated

# Recursively map all nodes that are within Tuples, Lists, and Dicts.
def map_value_nodes(node):
    sub_nodes = None
    if isinstance(node, ast.Tuple) or isinstance(node, ast.List):
        sub_nodes = dict([(idx, map_value_nodes(n)) for idx,n in enumerate(node.elts) ])
    elif isinstance(node, ast.Dict):
        sub_nodes = {}
        assert(len(node.keys) == len(node.values))
        for key, value in zip(node.keys,node.values):
            if isinstance(key, ast.Str):
                sub_nodes[key.s] = map_value_nodes(value)
            elif isinstance(key, ast.Num):
                sub_nodes[key.n] = map_value_nodes(value)
    if sub_nodes: return sub_nodes
    return node

def is_conan_expand_call(node):
    if not isinstance(node, ast.Call): return False
    if not isinstance(node.func, ast.Name): return False
    if node.func.id != "conan_expand": return False
    return True

# Traverse the mappings and schedule the replacements when the conan_expand function is found.
def compute_conan_expand_replacements(atok, value, mapping):
    if not isinstance(mapping, dict):
        # Base case, there is no hierarchical mapping information anymore.
        # Check if a replacement should be performed.
        if is_conan_expand_call(mapping):
            value_range = atok.get_text_range(mapping)
            return {value_range: format_expanded_value(value, mapping.col_offset-1)}
        return {}
    # Hierarchical mapping information is available, recurse if possible and collect results.
    replacements = {}
    for key, mapping_value in mapping.items():
        if isinstance(value, dict) or isinstance(value, list) or isinstance(value, tuple):
            replacements.update(compute_conan_expand_replacements(atok, value[key], mapping_value))
        # TODO support special types if needed
    return replacements

def expand_recipe(recipe_path, conanfile, output, additional_expansions=[]):
    atok = asttokens.ASTTokens(load(recipe_path), parse=True)

    # Iterate through the ast at root level and search the ConanFile class by name.
    conanclass_node = None
    for item in atok.tree.body:
        if not isinstance(item, ast.ClassDef): continue
        if item.name !=  conanfile.__name__: continue
        conanclass_node = item
        break
    assert(conanclass_node)

    # Iterate through the class and determine a mapping between class members and ast nodes.
    member_value_mapping = {}
    for node in conanclass_node.body:
        if not isinstance(node, ast.Assign): continue
        assert(len(node.targets) == 1)
        if isinstance(node.targets[0], ast.Name):
            member_value_mapping[node.targets[0].id] = map_value_nodes(node.value)
        # TODO only simple assignments are supported for now, i.e., tuple unpacking is not working atm

    # Calculate replacements by looking for conan_expand calls within the mapped nodes.
    replacements = {}
    for member, mapping in member_value_mapping.items():
        value = getattr(conanfile, member)
        replacements.update(compute_conan_expand_replacements(atok, value, mapping))

    # Check for missed conan_expand calls and emit warning.
    for node in ast.walk(atok.tree):
        if not is_conan_expand_call(node): continue
        if atok.get_text_range(node) in replacements: continue
        output.writeln("(Line %d:%d) WARNING: \'%s\' could not be expanded." % (node.lineno, node.col_offset, atok.get_text(node)),
                               front=Color.BRIGHT_RED)

    # Add program defined replacements.
    for trace in additional_expansions:
        assert(isinstance(trace, tuple) and len(trace) > 0)
        node = member_value_mapping[trace[0]]
        value = getattr(conanfile, trace[0])
        for element in trace[1:]:
            assert(element in node and element in value)
            node = node[element]
            value = value[element]
        node_range = atok.get_text_range(node)
        replacements[node_range] = format_expanded_value(value, node.col_offset-1)

    # Convert replacement dictionary into list and perform replacement.
    replacements = [ (range[0], range[1], value) for range, value in replacements.items() ]
    save(recipe_path, asttokens.util.replace(atok.text, replacements))

def create_options(conanfile):
    try:
        package_options = PackageOptions(getattr(conanfile, "options", None))
        options = Options(package_options)

        default_options = getattr(conanfile, "default_options", None)
        if default_options:
            if isinstance(default_options, (list, tuple)):
                default_values = OptionsValues(default_options)
            elif isinstance(default_options, str):
                default_values = OptionsValues.loads(default_options)
            else:
                raise ConanException("Please define your default_options as list or "
                                     "multiline string")
            options.values = default_values
        return options
    except Exception as e:
        raise ConanException("Error while initializing options. %s" % str(e))


def create_requirements(conanfile):
    try:
        # Actual requirements of this package
        if not hasattr(conanfile, "requires"):
            return Requirements()
        else:
            if not conanfile.requires:
                return Requirements()
            if isinstance(conanfile.requires, tuple):
                return Requirements(*conanfile.requires)
            else:
                return Requirements(conanfile.requires, )
    except Exception as e:
        raise ConanException("Error while initializing requirements. %s" % str(e))


def create_settings(conanfile, settings, local):
    try:
        defined_settings = getattr(conanfile, "settings", None)
        if isinstance(defined_settings, str):
            defined_settings = [defined_settings]
        current = defined_settings or {}
        settings.constraint(current, raise_undefined_field=not local)
        return settings
    except Exception as e:
        raise ConanException("Error while initializing settings. %s" % str(e))


def create_exports(conanfile):
    if not hasattr(conanfile, "exports"):
        return None
    else:
        if isinstance(conanfile.exports, str):
            return (conanfile.exports, )
        return conanfile.exports


def create_exports_sources(conanfile):
    if not hasattr(conanfile, "exports_sources"):
        return None
    else:
        if isinstance(conanfile.exports_sources, str):
            return (conanfile.exports_sources, )
        return conanfile.exports_sources


@contextmanager
def _env_and_python(conanfile):
    with environment_append(conanfile.env):
        with pythonpath(conanfile):
            yield


def get_env_context_manager(conanfile, without_python=False):
    if not conanfile.apply_env:
        return no_op()
    if without_python:
        return environment_append(conanfile.env)
    return _env_and_python(conanfile)


class ConanFile(object):
    """ The base class for all package recipes
    """

    name = None
    version = None  # Any str, can be "1.1" or whatever
    url = None  # The URL where this File is located, as github, to collaborate in package
    # The license of the PACKAGE, just a shortcut, does not replace or
    # change the actual license of the source code
    license = None
    author = None  # Main maintainer/responsible for the package, any format
    build_policy = None
    short_paths = False
    apply_env = True  # Apply environment variables from requires deps_env_info and profiles

    def __init__(self, output, runner, settings, user=None, channel=None, local=None):
        # User defined generators
        self.generators = self.generators if hasattr(self, "generators") else ["txt"]
        if isinstance(self.generators, str):
            self.generators = [self.generators]

        # User defined options
        self.options = create_options(self)
        self.requires = create_requirements(self)
        self.settings = create_settings(self, settings, local)
        try:
            if self.settings.os_build and self.settings.os:
                output.writeln("*"*60, front=Color.BRIGHT_RED)
                output.writeln("  This package defines both 'os' and 'os_build' ",
                               front=Color.BRIGHT_RED)
                output.writeln("  Please use 'os' for libraries and 'os_build'",
                               front=Color.BRIGHT_RED)
                output.writeln("  only for build-requires used for cross-building",
                               front=Color.BRIGHT_RED)
                output.writeln("*"*60, front=Color.BRIGHT_RED)
        except ConanException:
            pass
        self.exports = create_exports(self)
        self.exports_sources = create_exports_sources(self)
        # needed variables to pack the project
        self.cpp_info = None  # Will be initialized at processing time
        self.deps_cpp_info = DepsCppInfo()

        # environment variables declared in the package_info
        self.env_info = None  # Will be initialized at processing time
        self.deps_env_info = DepsEnvInfo()

        # user declared variables
        self.user_info = None
        # Keys are the package names, and the values a dict with the vars
        self.deps_user_info = DepsUserInfo()

        # an output stream (writeln, info, warn error)
        self.output = output
        # something that can run commands, as os.sytem
        self._runner = runner

        self.develop = False

        # user specified env variables
        self._env_values = EnvValues()  # Updated at runtime, user specified -e
        self._user = user
        self._channel = channel

        self.in_local_cache = False
        self.description = None
        # Vars to control the build steps (build(), package())
        self.should_configure = True
        self.should_build = True
        self.should_install = True
        self.should_test = True

    @property
    def env(self):
        """Apply the self.deps_env_info into a copy of self._env_values (will prioritize the
        self._env_values, user specified from profiles or -e first, then inherited)"""
        # Cannot be lazy cached, because it's called in configure node, and we still don't have
        # the deps_env_info objects available
        tmp_env_values = self._env_values.copy()
        tmp_env_values.update(self.deps_env_info)

        ret, multiple = tmp_env_values.env_dicts(self.name)
        ret.update(multiple)
        return ret

    @property
    def channel(self):
        if not self._channel:
            self._channel = os.getenv("CONAN_CHANNEL")
            if not self._channel:
                raise ConanException("CONAN_CHANNEL environment variable not defined, "
                                     "but self.channel is used in conanfile")
        return self._channel

    @property
    def user(self):
        if not self._user:
            self._user = os.getenv("CONAN_USERNAME")
            if not self._user:
                raise ConanException("CONAN_USERNAME environment variable not defined, "
                                     "but self.user is used in conanfile")
        return self._user

    def collect_libs(self, folder="lib"):
        self.output.warn("Use 'self.collect_libs' is deprecated, "
                         "use tools.collect_libs(self) instead")
        return tools.collect_libs(self, folder=folder)

    @property
    def build_policy_missing(self):
        return self.build_policy == "missing"

    @property
    def build_policy_always(self):
        return self.build_policy == "always"

    def source(self):
        pass

    def system_requirements(self):
        """ this method can be overwritten to implement logic for system package
        managers, as apt-get

        You can define self.global_system_requirements = True, if you want the installation
        to be for all packages (not depending on settings/options/requirements)
        """

    def config_options(self):
        """ modify options, probably conditioned to some settings. This call is executed
        before config_settings. E.g.
        if self.settings.os == "Windows":
            del self.options.shared  # shared/static not supported in win
        """

    def configure(self):
        """ modify settings, probably conditioned to some options. This call is executed
        after config_options. E.g.
        if self.options.header_only:
            self.settings.clear()
        This is also the place for conditional requirements
        """

    def build(self):
        """ build your project calling the desired build tools as done in the command line.
        E.g. self.run("cmake --build .") Or use the provided build helpers. E.g. cmake.build()
        """
        self.output.warn("This conanfile has no build step")

    def package(self):
        """ package the needed files from source and build folders.
        E.g. self.copy("*.h", src="src/includes", dst="includes")
        """
        self.output.warn("This conanfile has no package step")

    def package_info(self):
        """ define cpp_build_info, flags, etc
        """

    def run(self, command, output=True, cwd=None, win_bash=False, subsystem=None, msys_mingw=True,
            ignore_errors=False, run_environment=False):
        def _run():
            if not win_bash:
                return self._runner(command, output, os.path.abspath(RUN_LOG_NAME), cwd)
            # FIXME: run in windows bash is not using output
            return tools.run_in_windows_bash(self, bashcmd=command, cwd=cwd, subsystem=subsystem,
                                             msys_mingw=msys_mingw)
        if run_environment:
            with tools.run_environment(self):
                if os_info.is_macos:
                    command = 'DYLD_LIBRARY_PATH="%s" %s' % (os.environ.get('DYLD_LIBRARY_PATH', ''), command)
                retcode = _run()
        else:
            retcode = _run()

        if not ignore_errors and retcode != 0:
            raise ConanException("Error %d while executing %s" % (retcode, command))

        return retcode

    def package_id(self):
        """ modify the conans info, typically to narrow values
        eg.: conaninfo.package_references = []
        """

    def test(self):
        """ test the generated executable.
        E.g.  self.run("./example")
        """
        raise ConanException("You need to create a method 'test' in your test/conanfile.py")

    def __repr__(self):
        if self.name and self.version and self._channel and self._user:
            return "%s/%s@%s/%s" % (self.name, self.version, self.user, self.channel)
        elif self.name and self.version:
            return "%s/%s@PROJECT" % (self.name, self.version)
        else:
            return "PROJECT"
