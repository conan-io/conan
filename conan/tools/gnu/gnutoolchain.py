from conan.errors import ConanException
from conan.internal import check_duplicated_generator
from conan.internal.internal_tools import raise_on_universal_arch
from conan.tools.apple.apple import apple_min_version_flag, is_apple_os, to_apple_arch, \
    apple_sdk_path
from conan.tools.apple.apple import get_apple_sdk_fullname
from conan.tools.build import cmd_args_to_string, save_toolchain_args
from conan.tools.build.cross_building import cross_building
from conan.tools.build.flags import architecture_flag, build_type_flags, cppstd_flag, \
    build_type_link_flags, \
    libcxx_flags
from conan.tools.env import Environment
from conan.tools.gnu.get_gnu_triplet import _get_gnu_triplet
from conan.tools.microsoft import VCVars, msvc_runtime_flag, unix_path, check_min_vs, is_msvc
from conans.model.pkg_type import PackageType


class GnuToolchain:
    """
    GnuToolchain generator.

    Note: it's based on legacy AutotoolsToolchain but with a more modern and usable UX
    """
    def __init__(self, conanfile, namespace=None, prefix="/"):
        """
        :param conanfile: The current recipe object. Always use ``self``.
        :param namespace: This argument avoids collisions when you have multiple toolchain calls in
               the same recipe. By setting this argument, the *conanbuild.conf* file used to pass
               information to the build helper will be named as *<namespace>_conanbuild.conf*. The default
               value is ``None`` meaning that the name of the generated file is *conanbuild.conf*. This
               namespace must be also set with the same value in the constructor of the Autotools build
               helper so that it reads the information from the proper file.
        :param prefix: Folder to use for ``--prefix`` argument ("/" by default).
        """
        raise_on_universal_arch(conanfile)
        self._conanfile = conanfile
        self._namespace = namespace
        self._is_apple_system = is_apple_os(self._conanfile)
        self._prefix = prefix

        # Extra flags
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

        self.cppstd = cppstd_flag(self._conanfile)
        self.arch_flag = architecture_flag(self._conanfile.settings)
        self.libcxx, self.gcc_cxx11_abi = libcxx_flags(self._conanfile)
        self.fpic = self._conanfile.options.get_safe("fPIC")
        self.msvc_runtime_flag = self._get_msvc_runtime_flag()
        self.msvc_extra_flags = self._msvc_extra_flags()

        # Cross build triplets
        self.cross_build = {
            "host": {"triplet": self._conanfile.conf.get("tools.gnu:host_triplet")},
            "build": {"triplet": self._conanfile.conf.get("tools.gnu:build_triplet")}
        }
        if cross_building(self._conanfile):
            compiler = self._conanfile.settings.get_safe("compiler")
            # Host triplet
            if not self.cross_build["host"]["triplet"]:
                os_host = conanfile.settings.get_safe("os")
                arch_host = conanfile.settings.get_safe("arch")
                self.cross_build["host"] = _get_gnu_triplet(os_host, arch_host, compiler=compiler)
            # Build triplet
            if not self.cross_build["build"]["triplet"]:
                os_build = conanfile.settings_build.get_safe('os')
                arch_build = conanfile.settings_build.get_safe('arch')
                self.cross_build["build"] = _get_gnu_triplet(os_build, arch_build, compiler=compiler)

        sysroot = self._conanfile.conf.get("tools.build:sysroot")
        sysroot = sysroot.replace("\\", "/") if sysroot is not None else None
        self.sysroot_flag = "--sysroot {}".format(sysroot) if sysroot else None
        self.configure_args = {}
        self.autoreconf_args = {"--force": None, "--install": None}
        self.make_args = {}
        # Initializing configure arguments: triplets, shared flags, dirs flags, etc.
        self.configure_args.update(self._get_default_configure_shared_flags())
        self.configure_args.update(self._get_default_configure_install_flags())
        self.configure_args.update(self._get_default_triplets())
        # Apple stuff
        self.apple_arch_flag = None
        self.apple_isysroot_flag = None
        self.apple_min_version_flag = None
        self._resolve_apple_flags_and_variables()
        # MSVC common stuff
        # self._add_common_msvc_env_variables()

    def _resolve_apple_flags_and_variables(self):
        if not self._is_apple_system:
            return
        # SDK path is mandatory for cross-building
        sdk_path = apple_sdk_path(self._conanfile)
        if not sdk_path and self.cross_build:
            raise ConanException(
                "Apple SDK path not found. For cross-compilation, you must "
                "provide a valid SDK path in 'tools.apple:sdk_path' config."
            )
        # Calculating the main Apple flags
        os_sdk = get_apple_sdk_fullname(self._conanfile)
        os_version = self._conanfile.settings.get_safe("os.version")
        subsystem = self._conanfile.settings.get_safe("os.subsystem")
        self.apple_min_version_flag = apple_min_version_flag(os_version, os_sdk, subsystem)

        if self._conanfile.settings_build.get_safe('os') == "Macos":
            # SDK path is mandatory for cross-building
            sdk_path = apple_sdk_path(self._conanfile)
            if not sdk_path:
                raise ConanException("You must provide a valid SDK path for cross-compilation.")
            apple_arch = to_apple_arch(self._conanfile)
            # https://man.archlinux.org/man/clang.1.en#Target_Selection_Options
            self.apple_arch_flag = "-arch {}".format(apple_arch) if apple_arch else None
            # -isysroot makes all includes for your library relative to the build directory
            self.apple_isysroot_flag = "-isysroot {}".format(sdk_path) if sdk_path else None

    # def _add_common_msvc_env_variables(self):
    #     env = Environment()
    #     if is_msvc(self):
    #         compile_wrapper = unix_path(self, self.conf.get("user.automake:compile-wrapper",
    #                                                         check_type=str))
    #         ar_wrapper = unix_path(self, self.conf.get("user.automake:lib-wrapper", check_type=str))
    #         env.define("CC", f"{compile_wrapper} cl -nologo")
    #         env.define("CXX", f"{compile_wrapper} cl -nologo")
    #         env.define("LD", f"{compile_wrapper} link -nologo")
    #         env.define("AR", f"{ar_wrapper} \"lib -nologo\"")
    #         env.define("NM", "dumpbin -symbols")
    #         env.define("OBJDUMP", ":")
    #         env.define("RANLIB", ":")
    #         env.define("STRIP", ":")

    def _get_msvc_runtime_flag(self):
        flag = msvc_runtime_flag(self._conanfile)
        if flag:
            flag = "-{}".format(flag)
        return flag

    def _msvc_extra_flags(self):
        if is_msvc(self._conanfile) and check_min_vs(self._conanfile, "180", raise_invalid=False):
            return ["-FS"]
        return []

    def _add_msvc_flags(self, flags):
        # This is to avoid potential duplicate with users recipes -FS (alreday some in ConanCenter)
        return [f for f in self.msvc_extra_flags if f not in flags]

    @staticmethod
    def _filter_list_empty_fields(v):
        return list(filter(bool, v))

    @staticmethod
    def _dict_to_list(flags):
        return [f"{k}={v}" if v else k for k, v in flags.items()]

    @property
    def cxxflags(self):
        fpic = "-fPIC" if self.fpic else None
        ret = [self.libcxx, self.cppstd, self.arch_flag, fpic, self.msvc_runtime_flag,
               self.sysroot_flag]
        apple_flags = [self.apple_isysroot_flag, self.apple_arch_flag, self.apple_min_version_flag]
        conf_flags = self._conanfile.conf.get("tools.build:cxxflags", default=[], check_type=list)
        vs_flag = self._add_msvc_flags(self.extra_cxxflags)
        ret = ret + self.build_type_flags + apple_flags + self.extra_cxxflags + vs_flag + conf_flags
        return self._filter_list_empty_fields(ret)

    @property
    def cflags(self):
        fpic = "-fPIC" if self.fpic else None
        ret = [self.arch_flag, fpic, self.msvc_runtime_flag, self.sysroot_flag]
        apple_flags = [self.apple_isysroot_flag, self.apple_arch_flag, self.apple_min_version_flag]
        conf_flags = self._conanfile.conf.get("tools.build:cflags", default=[], check_type=list)
        vs_flag = self._add_msvc_flags(self.extra_cflags)
        ret = ret + self.build_type_flags + apple_flags + self.extra_cflags + vs_flag + conf_flags
        return self._filter_list_empty_fields(ret)

    @property
    def ldflags(self):
        ret = [self.arch_flag, self.sysroot_flag]
        apple_flags = [self.apple_isysroot_flag, self.apple_arch_flag, self.apple_min_version_flag]
        conf_flags = self._conanfile.conf.get("tools.build:sharedlinkflags", default=[],
                                              check_type=list)
        conf_flags.extend(self._conanfile.conf.get("tools.build:exelinkflags", default=[],
                                                   check_type=list))
        linker_scripts = self._conanfile.conf.get("tools.build:linker_scripts", default=[],
                                                  check_type=list)
        conf_flags.extend(["-T'" + linker_script + "'" for linker_script in linker_scripts])
        ret = ret + self.build_type_link_flags + apple_flags + self.extra_ldflags + conf_flags
        return self._filter_list_empty_fields(ret)

    @property
    def defines(self):
        conf_flags = self._conanfile.conf.get("tools.build:defines", default=[], check_type=list)
        ret = [self.ndebug, self.gcc_cxx11_abi] + self.extra_defines + conf_flags
        return self._filter_list_empty_fields(ret)

    def _get_default_configure_shared_flags(self):
        args = {}
        # Just add these flags if there's a shared option defined (never add to exe's)
        if self._conanfile.package_type is PackageType.SHARED:
            args = {"--enable-shared": None, "--disable-static": None}
        elif self._conanfile.package_type is PackageType.STATIC:
            args = {"--disable-shared": None, "--enable-static": None}
        return args

    def _get_default_configure_install_flags(self):
        configure_install_flags = {
            "--prefix": self._prefix
        }
        # If someone want arguments but not the defaults can pass them in args manually
        for flag_name, cppinfo_name in [("bindir", "bindirs"), ("sbindir", "bindirs"),
                                        ("libdir", "libdirs"), ("includedir", "includedirs"),
                                        ("oldincludedir", "includedirs"),
                                        ("datarootdir", "resdirs")]:
            elements = getattr(self._conanfile.cpp.package, cppinfo_name)
            cppinfo_value = f"${{prefix}}/{elements[0]}" if elements else None
            if cppinfo_value:
                configure_install_flags[f"--{flag_name}"] = cppinfo_value
        return configure_install_flags

    def _get_default_triplets(self):
        triplets = {}
        for context, info in self.cross_build.items():
            if info.get("triplet") is not None:
                triplets[f"--{context}"] = info["triplet"]
        return triplets

    def environment(self):
        env = Environment()
        compilers_by_conf = self._conanfile.conf.get("tools.build:compiler_executables", default={},
                                                     check_type=dict)
        if compilers_by_conf:
            compilers_mapping = {"c": "CC", "cpp": "CXX", "cuda": "NVCC", "fortran": "FC", "rc": "RC"}
            for comp, env_var in compilers_mapping.items():
                if comp in compilers_by_conf:
                    compiler = compilers_by_conf[comp]
                    # https://github.com/conan-io/conan/issues/13780
                    compiler = unix_path(self._conanfile, compiler)
                    env.define(env_var, compiler)
        env.append("CPPFLAGS", ["-D{}".format(d) for d in self.defines])
        env.append("CXXFLAGS", self.cxxflags)
        env.append("CFLAGS", self.cflags)
        env.append("LDFLAGS", self.ldflags)
        env.prepend_path("PKG_CONFIG_PATH", self._conanfile.generators_folder)
        return env

    def vars(self):
        return self.environment().vars(self._conanfile, scope="build")

    def generate(self, env=None, scope="build"):
        check_duplicated_generator(self, self._conanfile)
        env = env or self.environment()
        env = env.vars(self._conanfile, scope=scope)
        env.save_script("conanautotoolstoolchain")
        # Converts all the arguments into strings
        args = {
            "configure_args": cmd_args_to_string(self._dict_to_list(self.configure_args)),
            "make_args": cmd_args_to_string(self._dict_to_list(self.make_args)),
            "autoreconf_args": cmd_args_to_string(self._dict_to_list(self.autoreconf_args))
        }
        save_toolchain_args(args, namespace=self._namespace)
        VCVars(self._conanfile).generate(scope=scope)

"""
    def generate(self):
        env = VirtualBuildEnv(self)
        env.generate()

        tc = AutotoolsToolchain(self)
        yes_no = lambda v: "yes" if v else "no"
        tc.configure_args.extend([
            f'--with-pic={yes_no(self.options.get_safe("fPIC", True))}',
            f'--enable-assembly={yes_no(not self.options.get_safe("disable_assembly", False))}',
            f'--enable-fat={yes_no(self.options.get_safe("enable_fat", False))}',
            f'--enable-cxx={yes_no(self.options.enable_cxx)}',
            f'--srcdir={"../src"}', # Use relative path to avoid issues with #include "$srcdir/gmp-h.in" on Windows
        ])
        if is_msvc(self):
            tc.configure_args.extend([
                "ac_cv_c_restrict=restrict",
                "gmp_cv_asm_label_suffix=:",
                "lt_cv_sys_global_symbol_pipe=cat",  # added to get further in shared MSVC build, but it gets stuck later
            ])
            tc.extra_cxxflags.append("-EHsc")
            if check_min_vs(self, "180", raise_invalid=False):
                tc.extra_cflags.append("-FS")
                tc.extra_cxxflags.append("-FS")
        env = tc.environment() # Environment must be captured *after* setting extra_cflags, etc. to pick up changes
        if is_msvc(self):
            yasm_wrapper = unix_path(self, os.path.join(self.source_folder, "yasm_wrapper.sh"))
            yasm_machine = {
                "x86": "x86",
                "x86_64": "amd64",
            }[str(self.settings.arch)]
            ar_wrapper = unix_path(self, self.conf.get("user.automake:lib-wrapper"))
            dumpbin_nm = unix_path(self, os.path.join(self.source_folder, "dumpbin_nm.py"))
            env.define("CC", "cl -nologo")
            env.define("CCAS", f"{yasm_wrapper} -a x86 -m {yasm_machine} -p gas -r raw -f win32 -g null -X gnu")
            env.define("CXX", "cl -nologo")
            env.define("LD", "link -nologo")
            env.define("AR", f'{ar_wrapper} "lib -nologo"')
            env.define("NM", f"python {dumpbin_nm}")
        tc.generate(env)

"""
