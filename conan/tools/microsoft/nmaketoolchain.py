from conan.tools._compilers import cppstd_flag, build_type_flags, build_type_link_flags
from conan.tools.env import Environment
from conan.tools.microsoft.visual import msvc_runtime_flag, VCVars


class NMakeToolchain(object):
    """
    https://learn.microsoft.com/en-us/cpp/build/reference/running-nmake?view=msvc-170#toolsini-and-nmake
    We have also explored the usage of Tools.ini:
    https://learn.microsoft.com/en-us/cpp/build/reference/running-nmake?view=msvc-170
    but not possible, because it cannot include other files, it will also potentially collide with
    a user Tool.ini, without easy resolution. At least the environment is additive.
    """
    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        self._conanfile = conanfile

        # Flags
        self.extra_cflags = []
        self.extra_cxxflags = []
        self.extra_ldflags = []
        self.extra_defines = []

        # Defines
        self._ndebug = None
        build_type = self._conanfile.settings.get_safe("build_type")
        if build_type in ["Release", "RelWithDebInfo", "MinSizeRel"]:
            self._ndebug = "NDEBUG"

        self._build_type_flags = build_type_flags(self._conanfile.settings)
        self._build_type_link_flags = build_type_link_flags(self._conanfile.settings)

        self._cppstd = cppstd_flag(self._conanfile.settings)
        self._msvc_runtime_flag = self._get_msvc_runtime_flag()

    def _get_msvc_runtime_flag(self):
        flag = msvc_runtime_flag(self._conanfile)
        if flag:
            flag = f"/{flag}"
        return flag

    def _sanitized_options(self, options):
        return [f"{opt[0].replace('-', '/')}{opt[1:]}" for opt in options if len(opt) > 1]

    def _sanitized_defines(self, defines):
        sanitized_defines = []
        for define in defines:
            if "=" in define:
                # CL env-var can't accept '=' sign in /D option, it can be replaced by '#' sign:
                # https://learn.microsoft.com/en-us/cpp/build/reference/cl-environment-variables
                macro, value = define.split("=", 1)
                if not value:
                    sanitized_defines.append(f"/D{macro}")
                elif value.isnumeric():
                    sanitized_defines.append(f"/D{macro}#{value}")
                else:
                    # if value of macro is a string, it must be protected by protected quotes
                    sanitized_defines.append(f"/D{macro}#\\\"{value}\\\"")
            else:
                sanitized_defines.append(f"/D{define}")
        return sanitized_defines

    @property
    def _cflags(self):
        bt_flags = self._build_type_flags if self._build_type_flags else []
        rt_flags = [self._msvc_runtime_flag] if self._msvc_runtime_flag else []
        conf_cflags = self._conanfile.conf.get("tools.build:cflags", default=[], check_type=list)
        return self._sanitized_options(bt_flags + rt_flags + conf_cflags + self.extra_cflags)

    @property
    def _cxxflags(self):
        bt_flags = self._build_type_flags if self._build_type_flags else []
        rt_flags = [self._msvc_runtime_flag] if self._msvc_runtime_flag else []
        cppstd_flags = [self._cppstd] if self._cppstd else []
        conf_cxxflags = self._conanfile.conf.get("tools.build:cxxflags", default=[], check_type=list)
        return self._sanitized_options(bt_flags + rt_flags + cppstd_flags + conf_cxxflags + self.extra_cxxflags)

    @property
    def _ldflags(self):
        bt_ldflags = self._build_type_link_flags if self._build_type_link_flags else []
        conf_shared_ldflags = self._conanfile.conf.get("tools.build:sharedlinkflags", default=[], check_type=list)
        conf_exe_ldflags = self._conanfile.conf.get("tools.build:exelinkflags", default=[], check_type=list)
        return self._sanitized_options(bt_ldflags + conf_shared_ldflags + conf_exe_ldflags + self.extra_ldflags)

    @property
    def _defines(self):
        ndebug_defines = [self._ndebug] if self._ndebug else []
        conf_defines = self._conanfile.conf.get("tools.build:defines", default=[], check_type=list)
        return self._sanitized_defines(ndebug_defines + conf_defines + self.extra_defines)

    @property
    def _cl(self):
        nologo = ["/nologo"]
        conf_cflags = self._conanfile.conf.get("tools.build:cflags", default=[], check_type=list)
        return nologo + self._cxxflags + self._sanitized_options(conf_cflags) + self._defines

    @property
    def _link(self):
        nologo = ["/nologo"]
        return nologo + self._ldflags

    def environment(self):
        env = Environment()
        # Injection of compile flags in CL env-var:
        # https://learn.microsoft.com/en-us/cpp/build/reference/cl-environment-variables
        env.append("CL", self._cl)
        # Injection of link flags in _LINK_ env-var:
        # https://learn.microsoft.com/en-us/cpp/build/reference/linking
        env.append("_LINK_", self._link)
        # Also define some special env-vars which can override special NMake macros:
        # https://learn.microsoft.com/en-us/cpp/build/reference/special-nmake-macros
        conf_compilers = self._conanfile.conf.get("tools.build:compiler_executables", default={}, check_type=dict)
        if conf_compilers:
            compilers_mapping = {
                "AS": "asm",
                "CC": "c",
                "CPP": "cpp",
                "CXX": "cpp",
                "RC": "rc",
            }
            for env_var, comp in compilers_mapping.items():
                if comp in conf_compilers:
                    env.define(env_var, conf_compilers[comp])
        env.append("CFLAGS", self._cflags)
        env.append("CPPFLAGS", self._cxxflags)
        env.append("CXXFLAGS", self._cxxflags)
        return env

    def vars(self):
        return self.environment().vars(self._conanfile, scope="build")

    def generate(self, env=None, scope="build"):
        env = env or self.environment()
        env.vars(self._conanfile, scope=scope).save_script("conannmaketoolchain")
        VCVars(self._conanfile).generate(scope=scope)
