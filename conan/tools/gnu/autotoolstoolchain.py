from conan.tools._check_build_profile import check_using_build_profile
from conan.tools._compilers import architecture_flag, build_type_flags, cppstd_flag, \
    build_type_link_flags, libcxx_flags
from conan.tools.apple.apple import apple_min_version_flag, to_apple_arch, \
    apple_sdk_path
from conan.tools.build.cross_building import cross_building, get_cross_building_settings
from conan.tools.env import Environment
from conan.tools.files.files import save_toolchain_args
from conan.tools.gnu.get_gnu_triplet import _get_gnu_triplet
from conan.tools.microsoft import VCVars, is_msvc, msvc_runtime_flag, unix_path
from conans.errors import ConanException
from conans.tools import args_to_string, get_env
import os


class AutotoolsToolchain:
    def __init__(self, conanfile, namespace=None, compiler_wrapper=None, arlib_wrapper=None):
        self._conanfile = conanfile
        self._namespace = namespace
        self._compile_wrapper = compiler_wrapper
        self._arlib_wrapper = arlib_wrapper

        self.configure_args = self._default_configure_shared_flags() + self._default_configure_install_flags()
        self.autoreconf_args = self._default_autoreconf_flags()
        self.make_args = []

        # Flags
        self.extra_cxxflags = []
        self.extra_cflags = []
        self.extra_ldflags = []
        self.extra_defines = []

        # Defines
        self.ndebug = None
        build_type = self._conanfile.settings.get_safe("build_type")
        if build_type in ['Release', 'RelWithDebInfo', 'MinSizeRel']:
            self.ndebug = "NDEBUG"

        # TODO: This is also covering compilers like Visual Studio, necessary to test it (&remove?)
        self.build_type_flags = build_type_flags(self._conanfile.settings)
        self.build_type_link_flags = build_type_link_flags(self._conanfile.settings)

        self.cppstd = cppstd_flag(self._conanfile.settings)
        self.arch_flag = architecture_flag(self._conanfile.settings)
        self.libcxx, self.gcc_cxx11_abi = libcxx_flags(self._conanfile)
        self.fpic = self._conanfile.options.get_safe("fPIC")
        self.msvc_runtime_flag = self._get_msvc_runtime_flag()

        # standard build toolchains env vars
        self.cc = self._get_cc()
        self.cxx = self._get_cxx()
        self.ld = self._get_ld()
        self.ar = self._get_ar()
        self.nm = self._get_nm()
        self.objdump = self._get_objdump()
        self.ranlib = self._get_ranlib()
        self.strip = self._get_strip()

        # Cross build
        self._host = None
        self._build = None
        self._target = None

        self.apple_arch_flag = self.apple_isysroot_flag = None
        self.apple_min_version_flag = apple_min_version_flag(self._conanfile)

        self.sysroot_flag = None

        if cross_building(self._conanfile):
            os_build, arch_build, os_host, arch_host = get_cross_building_settings(self._conanfile)
            compiler = self._conanfile.settings.get_safe("compiler")
            self._host = _get_gnu_triplet(os_host, arch_host, compiler=compiler)
            self._build = _get_gnu_triplet(os_build, arch_build, compiler=compiler)

            # Apple Stuff
            if os_build == "Macos":
                sdk_path = apple_sdk_path(conanfile)
                apple_arch = to_apple_arch(self._conanfile)
                # https://man.archlinux.org/man/clang.1.en#Target_Selection_Options
                self.apple_arch_flag = "-arch {}".format(apple_arch) if apple_arch else None
                # -isysroot makes all includes for your library relative to the build directory
                self.apple_isysroot_flag = "-isysroot {}".format(sdk_path) if sdk_path else None

        sysroot = self._conanfile.conf.get("tools.build:sysroot")
        sysroot = sysroot.replace("\\", "/") if sysroot is not None else None
        self.sysroot_flag = "--sysroot {}".format(sysroot) if sysroot else None

        check_using_build_profile(self._conanfile)

    def _get_msvc_runtime_flag(self):
        flag = msvc_runtime_flag(self._conanfile)
        if flag:
            flag = "-{}".format(flag)
        return flag

    @staticmethod
    def _filter_list_empty_fields(v):
        return list(filter(bool, v))

    @property
    def cxxflags(self):
        fpic = "-fPIC" if self.fpic else None
        ret = [self.libcxx, self.cppstd, self.arch_flag, fpic, self.msvc_runtime_flag,
               self.sysroot_flag]
        apple_flags = [self.apple_isysroot_flag, self.apple_arch_flag, self.apple_min_version_flag]
        conf_flags = self._conanfile.conf.get("tools.build:cxxflags", default=[], check_type=list)
        ret = ret + self.build_type_flags + apple_flags + conf_flags + self.extra_cxxflags
        return self._filter_list_empty_fields(ret)

    @property
    def cflags(self):
        fpic = "-fPIC" if self.fpic else None
        ret = [self.arch_flag, fpic, self.msvc_runtime_flag, self.sysroot_flag]
        apple_flags = [self.apple_isysroot_flag, self.apple_arch_flag, self.apple_min_version_flag]
        conf_flags = self._conanfile.conf.get("tools.build:cflags", default=[], check_type=list)
        ret = ret + self.build_type_flags + apple_flags + conf_flags + self.extra_cflags
        return self._filter_list_empty_fields(ret)

    @property
    def ldflags(self):
        ret = [self.arch_flag, self.sysroot_flag]
        apple_flags = [self.apple_isysroot_flag, self.apple_arch_flag, self.apple_min_version_flag]
        conf_flags = self._conanfile.conf.get("tools.build:sharedlinkflags", default=[],
                                              check_type=list)
        conf_flags.extend(self._conanfile.conf.get("tools.build:exelinkflags", default=[],
                                                   check_type=list))
        ret = ret + apple_flags + conf_flags + self.build_type_link_flags + self.extra_ldflags
        return self._filter_list_empty_fields(ret)

    @property
    def defines(self):
        conf_flags = self._conanfile.conf.get("tools.build:defines", default=[], check_type=list)
        ret = [self.ndebug, self.gcc_cxx11_abi] + conf_flags + self.extra_defines
        return self._filter_list_empty_fields(ret)

    def _get_cc(self):
        return self._exe_env_var_to_unix_path(
            "CC",
            "cl" if is_msvc(self._conanfile) else None,
            ["-nologo"] if is_msvc(self._conanfile) else [],
            self._compile_wrapper,
        )

    def _get_cxx(self):
        return self._exe_env_var_to_unix_path(
            "CXX",
            "cl" if is_msvc(self._conanfile) else None,
            ["-nologo"] if is_msvc(self._conanfile) else [],
            self._compile_wrapper,
        )

    def _get_ld(self):
        return self._exe_env_var_to_unix_path(
            "LD",
            "link" if is_msvc(self._conanfile) else None,
            ["-nologo"] if is_msvc(self._conanfile) else [],
        )

    def _get_ar(self):
        return self._exe_env_var_to_unix_path(
            "AR",
            "lib" if is_msvc(self._conanfile) else None,
            ["-nologo"] if is_msvc(self._conanfile) else [],
            self._arlib_wrapper,
        )

    def _get_nm(self):
        return self._exe_env_var_to_unix_path(
            "NM",
            "dumpbin" if is_msvc(self._conanfile) else None,
            ["-nologo", "-symbols"] if is_msvc(self._conanfile) else [],
        )

    def _get_objdump(self):
        return self._exe_env_var_to_unix_path(
            "OBJDUMP",
            ":" if is_msvc(self._conanfile) else None,
        )

    def _get_ranlib(self):
        return self._exe_env_var_to_unix_path(
            "RANLIB",
            ":" if is_msvc(self._conanfile) else None,
        )

    def _get_strip(self):
        return self._exe_env_var_to_unix_path(
            "STRIP",
            ":" if is_msvc(self._conanfile) else None,
        )

    def _exe_env_var_to_unix_path(self, env_var, default=None, extra_options=[], wrapper=None):
        """
            Convenient method to convert env vars like CC, CXX or LD to values compatible with autotools.
            If env var doesn't exist, returns default.
        """
        exe = get_env(env_var)
        if exe:
            if os.path.exists(exe):
                exe = unix_path(self._conanfile, exe)
        else:
            exe = default
        if exe:
            if wrapper:
                if os.path.exists(wrapper):
                    wrapper = unix_path(self._conanfile, wrapper)
                exe = f"{wrapper} {exe}"
            for option in extra_options:
                if option not in exe:
                    exe += f" {option}"
        return exe

    def environment(self):
        env = Environment()
        for env_var, new_env_var_value in [
            ("CC", self.cc),
            ("CXX", self.cxx),
            ("LD", self.ld),
            ("AR", self.ar),
            ("NM", self.nm),
            ("OBJDUMP", self.objdump),
            ("RANLIB", self.ranlib),
            ("STRIP", self.strip),
        ]:
            if new_env_var_value and new_env_var_value != get_env(env_var):
                env.define(env_var, new_env_var_value)
        env.append("CPPFLAGS", ["-D{}".format(d) for d in self.defines])
        env.append("CXXFLAGS", self.cxxflags)
        env.append("CFLAGS", self.cflags)
        env.append("LDFLAGS", self.ldflags)
        env.prepend_path("PKG_CONFIG_PATH", self._conanfile.generators_folder)
        return env

    def vars(self):
        return self.environment().vars(self._conanfile, scope="build")

    def generate(self, env=None, scope="build"):
        env = env or self.environment()
        env = env.vars(self._conanfile, scope=scope)
        env.save_script("conanautotoolstoolchain")
        self.generate_args()
        VCVars(self._conanfile).generate(scope=scope)

    def _default_configure_shared_flags(self):
        args = []
        # Just add these flags if there's a shared option defined (never add to exe's)
        # FIXME: For Conan 2.0 use the package_type to decide if adding these flags or not
        try:
            if self._conanfile.options.shared:
                args.extend(["--enable-shared", "--disable-static"])
            else:
                args.extend(["--disable-shared", "--enable-static"])
        except ConanException:
            pass

        return args

    def _default_configure_install_flags(self):
        configure_install_flags = []

        def _get_argument(argument_name, cppinfo_name):
            elements = getattr(self._conanfile.cpp.package, cppinfo_name)
            return "--{}=${{prefix}}/{}".format(argument_name, elements[0]) if elements else ""

        # If someone want arguments but not the defaults can pass them in args manually
        configure_install_flags.extend(["--prefix=/",
                                       _get_argument("bindir", "bindirs"),
                                       _get_argument("sbindir", "bindirs"),
                                       _get_argument("libdir", "libdirs"),
                                       _get_argument("includedir", "includedirs"),
                                       _get_argument("oldincludedir", "includedirs"),
                                       _get_argument("datarootdir", "resdirs")])
        return [el for el in configure_install_flags if el]

    def _default_autoreconf_flags(self):
        return ["--force", "--install"]

    def generate_args(self):
        configure_args = []
        configure_args.extend(self.configure_args)
        user_args_str = args_to_string(self.configure_args)
        for flag, var in (("host", self._host), ("build", self._build), ("target", self._target)):
            if var and flag not in user_args_str:
                configure_args.append('--{}={}'.format(flag, var))

        args = {"configure_args": args_to_string(configure_args),
                "make_args":  args_to_string(self.make_args),
                "autoreconf_args": args_to_string(self.autoreconf_args)}

        save_toolchain_args(args, namespace=self._namespace)
