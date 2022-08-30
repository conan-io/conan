import fnmatch
from collections import OrderedDict

import six

from conans.errors import ConanException

BUILT_IN_CONFS = {
    "core:required_conan_version": "Raise if current version does not match the defined range.",
    "core.package_id:msvc_visual_incompatible": "Allows opting-out the fallback from the new msvc compiler to the Visual Studio compiler existing binaries",
    "core:default_profile": "Defines the default host profile ('default' by default)",
    "core:default_build_profile": "Defines the default build profile (None by default)",
    "tools.android:ndk_path": "Argument for the CMAKE_ANDROID_NDK",
    "tools.build:skip_test": "Do not execute CMake.test() and Meson.test() when enabled",
    "tools.build:jobs": "Default compile jobs number -jX Ninja, Make, /MP VS (default: max CPUs)",
    "tools.build:sysroot": "Pass the --sysroot=<tools.build:sysroot> flag if available. (None by default)",
    "tools.cmake.cmaketoolchain:generator": "User defined CMake generator to use instead of default",
    "tools.cmake.cmaketoolchain:find_package_prefer_config": "Argument for the CMAKE_FIND_PACKAGE_PREFER_CONFIG",
    "tools.cmake.cmaketoolchain:toolchain_file": "Use other existing file rather than conan_toolchain.cmake one",
    "tools.cmake.cmaketoolchain:user_toolchain": "Inject existing user toolchains at the beginning of conan_toolchain.cmake",
    "tools.cmake.cmaketoolchain:system_name": "Define CMAKE_SYSTEM_NAME in CMakeToolchain",
    "tools.cmake.cmaketoolchain:system_version": "Define CMAKE_SYSTEM_VERSION in CMakeToolchain",
    "tools.cmake.cmaketoolchain:system_processor": "Define CMAKE_SYSTEM_PROCESSOR in CMakeToolchain",
    "tools.cmake.cmaketoolchain.presets:max_schema_version": "Generate CMakeUserPreset.json compatible with the supplied schema version",
    "tools.env.virtualenv:auto_use": "Automatically activate virtualenv file generation",
    "tools.cmake.cmake_layout:build_folder_vars": "Settings and Options that will produce a different build folder and different CMake presets names",
    "tools.files.download:retry": "Number of retries in case of failure when downloading",
    "tools.files.download:retry_wait": "Seconds to wait between download attempts",
    "tools.gnu:make_program": "Indicate path to make program",
    "tools.gnu:define_libcxx11_abi": "Force definition of GLIBCXX_USE_CXX11_ABI=1 for libstdc++11",
    "tools.google.bazel:configs": "Define Bazel config file",
    "tools.google.bazel:bazelrc_path": "Defines Bazel rc-path",
    "tools.microsoft.msbuild:verbosity": "Verbosity level for MSBuild: 'Quiet', 'Minimal', 'Normal', 'Detailed', 'Diagnostic'",
    "tools.microsoft.msbuild:vs_version": "Defines the IDE version when using the new msvc compiler",
    "tools.microsoft.msbuild:max_cpu_count": "Argument for the /m when running msvc to build parallel projects",
    "tools.microsoft.msbuild:installation_path": "VS install path, to avoid auto-detect via vswhere, like C:/Program Files (x86)/Microsoft Visual Studio/2019/Community",
    "tools.microsoft.msbuilddeps:exclude_code_analysis": "Suppress MSBuild code analysis for patterns",
    "tools.microsoft.msbuildtoolchain:compile_options": "Dictionary with MSBuild compiler options",
    "tools.intel:installation_path": "Defines the Intel oneAPI installation root path",
    "tools.intel:setvars_args": "Custom arguments to be passed onto the setvars.sh|bat script from Intel oneAPI",
    "tools.system.package_manager:tool": "Default package manager tool: 'apt-get', 'yum', 'dnf', 'brew', 'pacman', 'choco', 'zypper', 'pkg' or 'pkgutil'",
    "tools.system.package_manager:mode": "Mode for package_manager tools: 'check' or 'install'",
    "tools.system.package_manager:sudo": "Use 'sudo' when invoking the package manager tools in Linux (False by default)",
    "tools.system.package_manager:sudo_askpass": "Use the '-A' argument if using sudo in Linux to invoke the system package manager (False by default)",
    "tools.apple.xcodebuild:verbosity": "Verbosity level for xcodebuild: 'verbose' or 'quiet",
    "tools.apple:enable_bitcode": "(boolean) Enable/Disable Bitcode Apple Clang flags",
    "tools.apple:enable_arc": "(boolean) Enable/Disable ARC Apple Clang flags",
    "tools.apple:enable_visibility": "(boolean) Enable/Disable Visibility Apple Clang flags",
    # Flags configuration
    "tools.build:cxxflags": "List of extra CXX flags used by different toolchains like CMakeToolchain, AutotoolsToolchain and MesonToolchain",
    "tools.build:cflags": "List of extra C flags used by different toolchains like CMakeToolchain, AutotoolsToolchain and MesonToolchain",
    "tools.build:defines": "List of extra definition flags used by different toolchains like CMakeToolchain and AutotoolsToolchain",
    "tools.build:sharedlinkflags": "List of extra flags used by CMakeToolchain for CMAKE_SHARED_LINKER_FLAGS_INIT variable",
    "tools.build:exelinkflags": "List of extra flags used by CMakeToolchain for CMAKE_EXE_LINKER_FLAGS_INIT variable",
}


def _is_profile_module(module_name):
    # These are the modules that are propagated to profiles and user recipes
    _user_modules = "tools.", "user."
    return any(module_name.startswith(user_module) for user_module in _user_modules)


# FIXME: Refactor all the next classes because they are mostly the same as
#        conan.tools.env.environment ones
class _ConfVarPlaceHolder:
    pass


class _ConfValue(object):

    def __init__(self, name, value):
        self._name = name
        self._value = value
        self._value_type = type(value)

    def __repr__(self):
        return repr(self._value)

    @property
    def value(self):
        if self._value_type is list and _ConfVarPlaceHolder in self._value:
            v = self._value[:]
            v.remove(_ConfVarPlaceHolder)
            return v
        return self._value

    def copy(self):
        return _ConfValue(self._name, self._value)

    def dumps(self):
        if self._value is None:
            return "{}=!".format(self._name)  # unset
        elif self._value_type is list and _ConfVarPlaceHolder in self._value:
            v = self._value[:]
            v.remove(_ConfVarPlaceHolder)
            return "{}={}".format(self._name, v)
        else:
            return "{}={}".format(self._name, self._value)

    def update(self, value):
        if self._value_type is dict:
            self._value.update(value)

    def remove(self, value):
        if self._value_type is list:
            self._value.remove(value)
        elif self._value_type is dict:
            self._value.pop(value, None)

    def append(self, value):
        if self._value_type is not list:
            raise ConanException("Only list-like values can append other values.")

        if isinstance(value, list):
            self._value.extend(value)
        else:
            self._value.append(value)

    def prepend(self, value):
        if self._value_type is not list:
            raise ConanException("Only list-like values can prepend other values.")

        if isinstance(value, list):
            self._value = value + self._value
        else:
            self._value.insert(0, value)

    def compose_conf_value(self, other):
        """
        self has precedence, the "other" will add/append if possible and not conflicting, but
        self mandates what to do. If self has define(), without placeholder, that will remain.
        :type other: _ConfValue
        """
        v_type = self._value_type
        o_type = other._value_type
        if v_type is list and o_type is list:
            try:
                index = self._value.index(_ConfVarPlaceHolder)
            except ValueError:  # It doesn't have placeholder
                pass
            else:
                new_value = self._value[:]  # do a copy
                new_value[index:index + 1] = other._value  # replace the placeholder
                self._value = new_value
        elif self._value is None or other._value is None \
            or (isinstance(self._value, six.string_types) and isinstance(self._value, six.string_types)):  # TODO: Python2, remove in 2.0
            # It means any of those values were an "unset" so doing nothing because we don't
            # really know the original value type
            pass
        elif o_type != v_type:
            raise ConanException("It's not possible to compose {} values "
                                 "and {} ones.".format(v_type.__name__, o_type.__name__))
        # TODO: In case of any other object types?


class Conf:

    # Putting some default expressions to check that any value could be false
    boolean_false_expressions = ("0", '"0"', "false", '"false"', "off")

    def __init__(self):
        # It being ordered allows for Windows case-insensitive composition
        self._values = OrderedDict()  # {var_name: [] of values, including separators}

    def __bool__(self):
        return bool(self._values)

    # TODO: Python2, remove in 2.0
    __nonzero__ = __bool__

    def __repr__(self):
        return "Conf: " + repr(self._values)

    def __eq__(self, other):
        """
        :type other: Conf
        """
        return other._values == self._values

    # TODO: Python2, remove in 2.0
    def __ne__(self, other):
        return not self.__eq__(other)

    def __getitem__(self, name):
        """
        DEPRECATED: it's going to disappear in Conan 2.0. Use self.get() instead.
        """
        # FIXME: Keeping backward compatibility
        return self.get(name)

    def __setitem__(self, name, value):
        """
        DEPRECATED: it's going to disappear in Conan 2.0.
        """
        # FIXME: Keeping backward compatibility
        self.define(name, value)  # it's like a new definition

    def __delitem__(self, name):
        """
        DEPRECATED: it's going to disappear in Conan 2.0.
        """
        # FIXME: Keeping backward compatibility
        del self._values[name]

    def items(self):
        # FIXME: Keeping backward compatibility
        for k, v in self._values.items():
            yield k, v.value

    @property
    def sha(self):
        # FIXME: Keeping backward compatibility
        return self.dumps()

    @staticmethod
    def _get_boolean_value(value):
        if type(value) is bool:
            return value
        elif str(value).lower() in Conf.boolean_false_expressions:
            return False
        else:
            return True

    def get(self, conf_name, default=None, check_type=None):
        """
        Get all the values belonging to the passed conf name.

        :param conf_name: conf name
        :param default: default value in case of conf does not have the conf_name key
        :param check_type: check the conf type(value) is the same as the given by this param.
                           There are two default smart conversions for bool and str types.
        """
        conf_value = self._values.get(conf_name)
        if conf_value:
            v = conf_value.value
            # Some smart conversions
            if check_type is bool and not isinstance(v, bool):
                # Perhaps, user has introduced a "false", "0" or even "off"
                return self._get_boolean_value(v)
            elif check_type is str and not isinstance(v, str):
                return str(v)
            elif v is None:  # value was unset
                return default
            elif check_type is not None and not isinstance(v, check_type):
                raise ConanException("[conf] {name} must be a {type}-like object. "
                                     "The value '{value}' introduced is a {vtype} "
                                     "object".format(name=conf_name, type=check_type.__name__,
                                                     value=v, vtype=type(v).__name__))
            return v
        else:
            return default

    def pop(self, conf_name, default=None):
        """
        Remove any key-value given the conf name
        """
        value = self.get(conf_name, default=default)
        self._values.pop(conf_name, None)
        return value

    @staticmethod
    def _validate_lower_case(name):
        if name != name.lower():
            raise ConanException("Conf '{}' must be lowercase".format(name))

    def copy(self):
        c = Conf()
        c._values = self._values.copy()
        return c

    def dumps(self):
        """ returns a string with a profile-like original definition, not the full environment
        values
        """
        return "\n".join([v.dumps() for v in reversed(self._values.values())])

    def define(self, name, value):
        self._validate_lower_case(name)
        self._values[name] = _ConfValue(name, value)

    def unset(self, name):
        """
        clears the variable, equivalent to a unset or set XXX=
        """
        self._values[name] = _ConfValue(name, None)

    def update(self, name, value):
        self._validate_lower_case(name)
        conf_value = _ConfValue(name, {})
        self._values.setdefault(name, conf_value).update(value)

    def append(self, name, value):
        self._validate_lower_case(name)
        conf_value = _ConfValue(name, [_ConfVarPlaceHolder])
        self._values.setdefault(name, conf_value).append(value)

    def prepend(self, name, value):
        self._validate_lower_case(name)
        conf_value = _ConfValue(name, [_ConfVarPlaceHolder])
        self._values.setdefault(name, conf_value).prepend(value)

    def remove(self, name, value):
        conf_value = self._values.get(name)
        if conf_value:
            conf_value.remove(value)
        else:
            raise ConanException("Conf {} does not exist.".format(name))

    def compose_conf(self, other):
        """
        :param other: other has less priority than current one
        :type other: Conf
        """
        for k, v in other._values.items():
            existing = self._values.get(k)
            if existing is None:
                self._values[k] = v.copy()
            else:
                existing.compose_conf_value(v)
        return self

    def filter_user_modules(self):
        result = Conf()
        for k, v in self._values.items():
            if _is_profile_module(k):
                result._values[k] = v
        return result


class ConfDefinition:

    actions = (("+=", "append"), ("=+", "prepend"),
               ("=!", "unset"), ("=", "define"))

    def __init__(self):
        self._pattern_confs = OrderedDict()

    def __repr__(self):
        return "ConfDefinition: " + repr(self._pattern_confs)

    def __bool__(self):
        return bool(self._pattern_confs)

    __nonzero__ = __bool__

    def __getitem__(self, module_name):
        """
        DEPRECATED: it's going to disappear in Conan 2.0. Use self.get() instead.
        if a module name is requested for this, it goes to the None-Global config by default
        """
        pattern, name = self._split_pattern_name(module_name)
        return self._pattern_confs.get(pattern, Conf()).get(name)

    def __delitem__(self, module_name):
        """
        DEPRECATED: it's going to disappear in Conan 2.0.  Use self.pop() instead.
        if a module name is requested for this, it goes to the None-Global config by default
        """
        pattern, name = self._split_pattern_name(module_name)
        del self._pattern_confs.get(pattern, Conf())[name]

    def get(self, conf_name, default=None, check_type=None):
        """
        Get the value of the  conf name requested and convert it to the [type]-like passed.
        """
        pattern, name = self._split_pattern_name(conf_name)
        return self._pattern_confs.get(pattern, Conf()).get(name, default=default,
                                                            check_type=check_type)

    def pop(self, conf_name, default=None):
        """
        Remove the conf name passed.
        """
        pattern, name = self._split_pattern_name(conf_name)
        return self._pattern_confs.get(pattern, Conf()).pop(name, default=default)

    @staticmethod
    def _split_pattern_name(pattern_name):
        if pattern_name.count(":") >= 2:
            pattern, name = pattern_name.split(":", 1)
        else:
            pattern, name = None, pattern_name
        return pattern, name

    def get_conanfile_conf(self, ref):
        """ computes package-specific Conf
        it is only called when conanfile.buildenv is called
        the last one found in the profile file has top priority
        """
        result = Conf()
        for pattern, conf in self._pattern_confs.items():
            if pattern is None or fnmatch.fnmatch(str(ref), pattern):
                # Latest declared has priority, copy() necessary to not destroy data
                result = conf.copy().compose_conf(result)
        return result

    def update_conf_definition(self, other):
        """
        :type other: ConfDefinition
        :param other: The argument profile has priority/precedence over the current one.
        """
        for pattern, conf in other._pattern_confs.items():
            self._update_conf_definition(pattern, conf)

    def _update_conf_definition(self, pattern, conf):
        existing = self._pattern_confs.get(pattern)
        if existing:
            self._pattern_confs[pattern] = conf.compose_conf(existing)
        else:
            self._pattern_confs[pattern] = conf

    def rebase_conf_definition(self, other):
        """
        for taking the new global.conf and composing with the profile [conf]
        :type other: ConfDefinition
        """
        for pattern, conf in other._pattern_confs.items():
            new_conf = conf.filter_user_modules()  # Creates a copy, filtered
            existing = self._pattern_confs.get(pattern)
            if existing:
                existing.compose_conf(new_conf)
            else:
                self._pattern_confs[pattern] = new_conf

    def update(self, key, value, profile=False, method="define"):
        """
        Define/append/prepend/unset any Conf line
        >> update("tools.microsoft.msbuild:verbosity", "Detailed")
        """
        pattern, name = self._split_pattern_name(key)

        if not _is_profile_module(name):
            if profile:
                raise ConanException("[conf] '{}' not allowed in profiles".format(key))
            if pattern is not None:
                raise ConanException("Conf '{}' cannot have a package pattern".format(key))

        # strip whitespaces before/after =
        # values are not strip() unless they are a path, to preserve potential whitespaces
        name = name.strip()

        # When loading from profile file, latest line has priority
        conf = Conf()
        if method == "unset":
            conf.unset(name)
        else:
            getattr(conf, method)(name, value)
        # Update
        self._update_conf_definition(pattern, conf)

    def as_list(self):
        result = []
        for pattern, conf in self._pattern_confs.items():
            for name, value in sorted(conf.items()):
                if pattern:
                    result.append(("{}:{}".format(pattern, name), value))
                else:
                    result.append((name, value))
        return result

    def dumps(self):
        result = []
        for pattern, conf in self._pattern_confs.items():
            if pattern is None:
                result.append(conf.dumps())
            else:
                result.append("\n".join("{}:{}".format(pattern, line) if line else ""
                                        for line in conf.dumps().splitlines()))
        if result:
            result.append("")
        return "\n".join(result)

    @staticmethod
    def _get_evaluated_value(__v):
        """
        Function to avoid eval() catching local variables
        """
        try:
            # Isolated eval
            parsed_value = eval(__v)
            if isinstance(parsed_value, str):  # xxx:xxx = "my string"
                # Let's respect the quotes introduced by any user
                parsed_value = '"{}"'.format(parsed_value)
        except:
            # It means eval() failed because of a string without quotes
            parsed_value = __v.strip()
        return parsed_value

    def loads(self, text, profile=False):
        self._pattern_confs = {}

        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for op, method in ConfDefinition.actions:
                tokens = line.split(op, 1)
                if len(tokens) != 2:
                    continue
                pattern_name, value = tokens
                parsed_value = ConfDefinition._get_evaluated_value(value)
                self.update(pattern_name, parsed_value, profile=profile, method=method)
                break
            else:
                raise ConanException("Bad conf definition: {}".format(line))
