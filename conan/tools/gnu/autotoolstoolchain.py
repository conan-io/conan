from conan.internal import check_duplicated_generator
from conan.tools.apple.apple import apple_min_version_flag, to_apple_arch
from conan.tools.apple.apple import get_apple_sdk_fullname
from conan.tools.build import cmd_args_to_string
from conan.tools.build.cross_building import cross_building
from conan.tools.build.flags import architecture_flag, build_type_flags, cppstd_flag, build_type_link_flags, libcxx_flags
from conan.tools.env import Environment
from conan.tools.files.files import save_toolchain_args
from conan.tools.gnu.get_gnu_triplet import _get_gnu_triplet
from conan.tools.microsoft import VCVars, msvc_runtime_flag
from conans.errors import ConanException


class AutotoolsToolchain:
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
        self._conanfile = conanfile
        self._namespace = namespace
        self._prefix = prefix

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

        # Cross build triplets
        self._host = self._conanfile.conf.get("tools.gnu:host_triplet")
        self._build = None
        self._target = None

        self.apple_arch_flag = self.apple_isysroot_flag = None

        os_sdk = get_apple_sdk_fullname(conanfile)
        os_version = conanfile.settings.get_safe("os.version")
        subsystem = conanfile.settings.get_safe("os.subsystem")
        self.apple_min_version_flag = apple_min_version_flag(os_version, os_sdk, subsystem)

        self.sysroot_flag = None

        if cross_building(self._conanfile):
            os_host = conanfile.settings.get_safe("os")
            arch_host = conanfile.settings.get_safe("arch")
            os_build = conanfile.settings_build.get_safe('os')
            arch_build = conanfile.settings_build.get_safe('arch')
            compiler = self._conanfile.settings.get_safe("compiler")
            if not self._host:
                self._host = _get_gnu_triplet(os_host, arch_host, compiler=compiler)
            self._build = _get_gnu_triplet(os_build, arch_build, compiler=compiler)

            # Apple Stuff
            if os_build == "Macos":
                # SDK path is mandatory for cross-building
                sdk_path = conanfile.conf["tools.apple:sdk_path"]
                if not sdk_path:
                    raise ConanException("You must provide a valid SDK path for cross-compilation.")
                apple_arch = to_apple_arch(self._conanfile)
                # https://man.archlinux.org/man/clang.1.en#Target_Selection_Options
                self.apple_arch_flag = "-arch {}".format(apple_arch) if apple_arch else None
                # -isysroot makes all includes for your library relative to the build directory
                self.apple_isysroot_flag = "-isysroot {}".format(sdk_path) if sdk_path else None

        sysroot = self._conanfile.conf.get("tools.build:sysroot")
        sysroot = sysroot.replace("\\", "/") if sysroot is not None else None
        self.sysroot_flag = "--sysroot {}".format(sysroot) if sysroot else None

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

    def environment(self):
        env = Environment()
        compilers_by_conf = self._conanfile.conf.get("tools.build:compiler_executables", default={}, check_type=dict)
        if compilers_by_conf:
            compilers_mapping = {"c": "CC", "cpp": "CXX", "cuda": "NVCC", "fortran": "FC"}
            for comp, env_var in compilers_mapping.items():
                if comp in compilers_by_conf:
                    env.define(env_var, compilers_by_conf[comp])
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
        configure_install_flags.extend([f"--prefix={self._prefix}",
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
        user_args_str = cmd_args_to_string(self.configure_args)
        for flag, var in (("host", self._host), ("build", self._build), ("target", self._target)):
            if var and flag not in user_args_str:
                configure_args.append('--{}={}'.format(flag, var))

        args = {"configure_args": cmd_args_to_string(configure_args),
                "make_args":  cmd_args_to_string(self.make_args),
                "autoreconf_args": cmd_args_to_string(self.autoreconf_args)}

        save_toolchain_args(args, namespace=self._namespace)
