import fnmatch
from collections import OrderedDict

from conans.errors import ConanException


DEFAULT_CONFIGURATION = {
    "core:required_conan_version": "Raise if current version does not match the defined range.",
    "core.package_id:msvc_visual_incompatible": "Allows opting-out the fallback from the new msvc compiler to the Visual Studio compiler existing binaries",
    "core:default_profile": "Defines the default host profile ('default' by default)",
    "core:default_build_profile": "Defines the default build profile (None by default)",
    "tools.android:ndk_path": "Argument for the CMAKE_ANDROID_NDK",
    "tools.build:skip_test": "Do not execute CMake.test() and Meson.test() when enabled",
    "tools.build:jobs": "Default compile jobs number -jX Ninja, Make, /MP VS (default: max CPUs)",
    "tools.cmake.cmaketoolchain:generator": "User defined CMake generator to use instead of default",
    "tools.cmake.cmaketoolchain:find_package_prefer_config": "Argument for the CMAKE_FIND_PACKAGE_PREFER_CONFIG",
    "tools.cmake.cmaketoolchain:toolchain_file": "Use other existing file rather than conan_toolchain.cmake one",
    "tools.cmake.cmaketoolchain:user_toolchain": "Inject existing user toolchain at the beginning of conan_toolchain.cmake",
    "tools.cmake.cmaketoolchain:system_name": "Define CMAKE_SYSTEM_NAME in CMakeToolchain",
    "tools.cmake.cmaketoolchain:system_version": "Define CMAKE_SYSTEM_VERSION in CMakeToolchain",
    "tools.cmake.cmaketoolchain:system_processor": "Define CMAKE_SYSTEM_PROCESSOR in CMakeToolchain",
    "tools.env.virtualenv:auto_use": "Automatically activate virtualenv file generation",
    "tools.files.download:retry": "Number of retries in case of failure when downloading",
    "tools.files.download:retry_wait": "Seconds to wait between download attempts",
    "tools.gnu:make_program": "Indicate path to make program",
    "tools.gnu:define_libcxx11_abi": "Force definition of GLIBCXX_USE_CXX11_ABI=1 for libstdc++11",
    "tools.google.bazel:config": "Define Bazel config file",
    "tools.google.bazel:bazelrc_path": "Defines Bazel rc-path",
    "tools.microsoft.msbuild:verbosity": "Verbosity level for MSBuild: "
                                         "'Quiet', 'Minimal', 'Normal', 'Detailed', 'Diagnostic'",
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
}


def _is_profile_module(module_name):
    # These are the modules that are propagated to profiles and user recipes
    _user_modules = "tools.", "user."
    return any(module_name.startswith(user_module) for user_module in _user_modules)


class _ConfVarPlaceHolder:
    pass


class _ConfValue:
    def __init__(self, name, value=_ConfVarPlaceHolder, separator=" ", path=False):
        self._name = name
        self._values = [] if value is None else value if isinstance(value, list) else [value]
        self._path = path
        self._sep = separator

    def __repr__(self):
        return "ConfValues: " + repr(self._values)

    @property
    def values(self):
        return self._values

    def dumps(self):
        result = []
        path = "(path)" if self._path else ""
        if not self._values:  # Empty means unset
            result.append("{}=!".format(self._name))
        elif _ConfVarPlaceHolder in self._values:
            index = self._values.index(_ConfVarPlaceHolder)
            for v in self._values[:index]:
                result.append("{}=+{}{}".format(self._name, path, v))
            for v in self._values[index+1:]:
                result.append("{}+={}{}".format(self._name, path, v))
        else:
            append = ""
            for v in self._values:
                result.append("{}{}={}{}".format(self._name, append, path, v))
                append = "+"
        return "\n".join(result)

    def copy(self):
        return _ConfValue(self._name, self._values, self._sep, self._path)

    def remove(self, value):
        self._values.remove(value)

    def append(self, value, separator=None):
        if separator is not None:
            self._sep = separator
        if isinstance(value, list):
            self._values.extend(value)
        else:
            self._values.append(value)

    def prepend(self, value, separator=None):
        if separator is not None:
            self._sep = separator
        if isinstance(value, list):
            self._values = value + self._values
        else:
            self._values.insert(0, value)

    def compose_conf_value(self, other):
        """
        :type other: _ConfValue
        """
        try:
            index = self._values.index(_ConfVarPlaceHolder)
        except ValueError:  # It doesn't have placeholder
            pass
        else:
            new_value = self._values[:]  # do a copy
            new_value[index:index + 1] = other._values  # replace the placeholder
            self._values = new_value


class Conf:

    def __init__(self):
        # It being ordered allows for Windows case-insensitive composition
        self._values = OrderedDict()  # {var_name: [] of values, including separators}

    def __bool__(self):
        return bool(self._values)

    __nonzero__ = __bool__

    def __getitem__(self, name):
        # FIXME: Keeping backward compatibility
        conf = self._values.get(name)
        if conf is not None:
            values = conf.values
            if len(values) == 1:
                return values[0]  # single value
            else:
                return values  # list of values

    def __setitem__(self, name, value):
        # FIXME: Keeping backward compatibility
        self.define(name, value)  # it's like a new definition

    def __delitem__(self, name):
        # FIXME: Keeping backward compatibility
        del self._values[name]

    @staticmethod
    def _validate_lower_case(name):
        if name != name.lower():
            raise ConanException("Conf '{}' must be lowercase".format(name))

    def items(self):
        for k, v in self._values.items():
            # FIXME: Keeping backward compatibility
            values = v.values
            if len(values) == 1:
                yield k, values[0]  # single value
            else:
                yield k, values  # list of values

    def copy(self):
        e = Conf()
        e._values = self._values.copy()
        return e

    def __repr__(self):
        return "Conf: " + repr(self._values)

    def dumps(self):
        """ returns a string with a profile-like original definition, not the full environment
        values
        """
        return "\n".join([v.dumps() for v in reversed(self._values.values())])

    def define(self, name, value, separator=" "):
        self._validate_lower_case(name)
        self._values[name] = _ConfValue(name, value, separator, path=False)

    def unset(self, name):
        """
        clears the variable, equivalent to a unset or set XXX=
        """
        self._values[name] = _ConfValue(name, None)

    def append(self, name, value, separator=None):
        self._validate_lower_case(name)
        self._values.setdefault(name, _ConfValue(name)).append(value, separator)

    def prepend(self, name, value, separator=None):
        self._validate_lower_case(name)
        self._values.setdefault(name, _ConfValue(name)).prepend(value, separator)

    def remove(self, name, value):
        self._values[name].remove(value)

    def compose_conf(self, other):
        """
        self has precedence, the "other" will add/append if possible and not conflicting, but
        self mandates what to do. If self has define(), without placeholder, that will remain
        :type other: Conf
        """
        for k, v in other._values.items():
            existing = self._values.get(k)
            if existing is None:
                self._values[k] = v.copy()
            else:
                existing.compose_conf_value(v)
        return self

    def __eq__(self, other):
        """
        :type other: Conf
        """
        return other._values == self._values

    def __ne__(self, other):
        return not self.__eq__(other)

    def filter_user_modules(self):
        result = Conf()
        for k, v in self._values.items():
            if _is_profile_module(k):
                result._values[k] = v
        return result

    @property
    def sha(self):
        result = []
        for k, v in sorted(self._values.items()):
            result.append("{}={}".format(k, v))
        return "\n".join(result)


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
        """ if a module name is requested for this, always goes to the None-Global config
        """
        return self._pattern_confs.get(None, Conf())[module_name]

    def __delitem__(self, module_name):
        """ if a module name is requested for this, always goes to the None-Global config
        """
        del self._pattern_confs.get(None, Conf())[module_name]

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
        if key.count(":") >= 2:
            pattern, name = key.split(":", 1)
        else:
            pattern, name = None, key

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
            getattr(conf, method)(name, value.strip())
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
                self.update(pattern_name, value, profile=profile, method=method)
                break
            else:
                raise ConanException("Bad conf definition: {}".format(line))
