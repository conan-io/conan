import fnmatch

from conans.errors import ConanException


DEFAULT_CONFIGURATION = {
    "core:required_conan_version": "Raise if current version does not match the defined range.",
    "core:non_interactive": "Disable interactive user input, raises error if input necessary",
    "core.package_id:msvc_visual_incompatible": "Allows opting-out the fallback from the new msvc compiler to the Visual Studio compiler existing binaries",
    "core:default_profile": "Defines the default host profile ('default' by default)",
    "core:default_build_profile": "Defines the default build profile (None by default)",
    "core.upload:retry": "Number of retries in case of failure when uploading to Conan server",
    "core.upload:retry_wait": "Seconds to wait between upload attempts to Conan server",
    "core.download:parallel": "Number of concurrent threads to download packages",
    "core.download:retry": "Number of retries in case of failure when downloading from Conan server",
    "core.download:retry_wait": "Seconds to wait between download attempts from Conan server",
    # General HTTP(python-requests) configuration
    "core.net.http:max_retries": "Maximum number of connection retries (requests library)",
    "core.net.http:timeout": "Number of seconds without response to timeout (requests library)",
    "core.net.http:no_proxy_match": "List of urls to skip from proxies configuration",
    "core.net.http:proxies": "Dictionary containing the proxy configuration",
    "core.net.http:cacert_path": "Path containing a custom Cacert file",
    "core.net.http:client_cert": "Path or tuple of files containing a client cert (and key)",
    "core.net.http:clean_system_proxy": "If defined, the proxies system env-vars will be discarded",
    # Gzip compression
    "core.gzip:compresslevel": "The Gzip compresion level for Conan artifacts (default=9)",
    # Tools
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
    "tools.intel:setvars_args": "Custom arguments to be passed onto the setvars.sh|bat script from Intel oneAPI"
}


def _is_profile_module(module_name):
    # These are the modules that are propagated to profiles and user recipes
    _user_modules = "tools.", "user."
    return any(module_name.startswith(user_module) for user_module in _user_modules)


class Conf(object):

    def __init__(self):
        self._values = {}  # property: value

    def __getitem__(self, name):
        return self._values.get(name)

    def get(self, conf_name, conf_type=None, conf_default=None):
        v = self._values.get(conf_name)
        if v is not None:
            if conf_type is not None:
                try:
                    v = conf_type(v)
                except Exception:
                    raise ConanException(f"Conf '{conf_name}' value '{v}' "
                                         f"must be '{conf_type.__name__}'")
        else:
            v = conf_default
        return v

    def __setitem__(self, name, value):
        if name != name.lower():
            raise ConanException("Conf '{}' must be lowercase".format(name))
        self._values[name] = value

    def __delitem__(self, name):
        del self._values[name]

    def __repr__(self):
        return "Conf: " + repr(self._values)

    def items(self):
        return self._values.items()

    def filter_user_modules(self):
        result = Conf()
        for k, v in self._values.items():
            if _is_profile_module(k):
                result._values[k] = v
        return result

    def update(self, other):
        """
        :param other: has more priority than current one
        :type other: Conf
        """
        self._values.update(other._values)

    def compose_conf(self, other):
        """
        :param other: other has less priority than current one
        :type other: Conf
        """
        for k, v in other._values.items():
            if k not in self._values:
                self._values[k] = v

    @property
    def sha(self):
        result = ["[conf]"]
        for k, v in sorted(self._values.items()):
            result.append("{}={}".format(k, v))
        return "\n".join(result)


class ConfDefinition(object):
    def __init__(self):
        self._pattern_confs = {}  # pattern (including None) => Conf

    def __bool__(self):
        return bool(self._pattern_confs)

    def __repr__(self):
        return "ConfDefinition: " + repr(self._pattern_confs)

    def __getitem__(self, module_name):
        """ if a module name is requested for this, always goes to the None-Global config
        """
        return self._pattern_confs.get(None, Conf())[module_name]

    def __delitem__(self, module_name):
        """ if a module name is requested for this, always goes to the None-Global config
        """
        del self._pattern_confs.get(None, Conf())[module_name]

    def get(self, conf_name, conf_type=None, conf_default=None):
        return self._pattern_confs.get(None, Conf()).get(conf_name, conf_type, conf_default)

    def get_conanfile_conf(self, ref_str):
        result = Conf()
        for pattern, conf in self._pattern_confs.items():
            if pattern is None or (ref_str is not None and fnmatch.fnmatch(ref_str, pattern)):
                result.update(conf)
        return result

    def update_conf_definition(self, other):
        """
        This is used for composition of profiles [conf] section
        :type other: ConfDefinition
        """
        for k, v in other._pattern_confs.items():
            existing = self._pattern_confs.get(k)
            if existing:
                existing.update(v)
            else:
                self._pattern_confs[k] = v

    def rebase_conf_definition(self, other):
        """
        for taking the new global.conf and composing with the profile [conf]
        :type other: ConfDefinition
        """
        for k, v in other._pattern_confs.items():
            new_v = v.filter_user_modules()  # Creates a copy, filtered
            existing = self._pattern_confs.get(k)
            if existing:
                new_v.update(existing)
            self._pattern_confs[k] = new_v

    def as_list(self):
        result = []
        # It is necessary to convert the None for sorting
        for pattern, conf in sorted(self._pattern_confs.items(),
                                    key=lambda x: ("", x[1]) if x[0] is None else x):
            for name, value in sorted(conf.items()):
                if pattern:
                    result.append(("{}:{}".format(pattern, name), value))
                else:
                    result.append((name, value))
        return result

    def dumps(self):
        result = []
        for name, value in self.as_list():
            result.append("{}={}".format(name, value))
        return "\n".join(result)

    def loads(self, text, profile=False):
        self._pattern_confs = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                left, value = line.split("=", 1)
            except ValueError:
                raise ConanException("Error while parsing conf value '{}'".format(line))
            else:
                self.update(left.strip(), value.strip(), profile=profile)

    def update(self, key, value, profile=False):
        """
        Add/update a new/existing Conf line

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

        conf = self._pattern_confs.setdefault(pattern, Conf())
        conf[name] = value
