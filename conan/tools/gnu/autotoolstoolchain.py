from conan.errors import ConanException
from conan.internal import check_duplicated_generator
from conan.internal.internal_tools import raise_on_universal_arch
from conan.tools.apple.apple import is_apple_os, resolve_apple_flags
from conan.tools.build import cmd_args_to_string, save_toolchain_args
from conan.tools.build.cross_building import cross_building
from conan.tools.build.flags import architecture_flag, build_type_flags, cppstd_flag, \
    build_type_link_flags, \
    libcxx_flags
from conan.tools.env import Environment
from conan.tools.gnu.get_gnu_triplet import _get_gnu_triplet
from conan.tools.microsoft import VCVars, msvc_runtime_flag, unix_path, check_min_vs, is_msvc
from conans.model.pkg_type import PackageType


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
        raise_on_universal_arch(conanfile)

        self._conanfile = conanfile
        self._namespace = namespace
        self._prefix = prefix

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

        self.cppstd = cppstd_flag(self._conanfile)
        self.arch_flag = architecture_flag(self._conanfile.settings)
        self.libcxx, self.gcc_cxx11_abi = libcxx_flags(self._conanfile)
        self.fpic = self._conanfile.options.get_safe("fPIC")
        self.msvc_runtime_flag = self._get_msvc_runtime_flag()
        self.msvc_extra_flags = self._msvc_extra_flags()

        # Cross build triplets
        self._host = self._conanfile.conf.get("tools.gnu:host_triplet")
        self._build = self._conanfile.conf.get("tools.gnu:build_triplet")
        self._target = None

        is_cross_building = cross_building(self._conanfile)
        if is_cross_building:
            os_host = conanfile.settings.get_safe("os")
            arch_host = conanfile.settings.get_safe("arch")
            os_build = conanfile.settings_build.get_safe('os')
            arch_build = conanfile.settings_build.get_safe('arch')

            compiler = self._conanfile.settings.get_safe("compiler")
            if not self._host:
                self._host = _get_gnu_triplet(os_host, arch_host, compiler=compiler)["triplet"]
            # Build triplet
            if not self._build:
                self._build = _get_gnu_triplet(os_build, arch_build, compiler=compiler)["triplet"]

        sysroot = self._conanfile.conf.get("tools.build:sysroot")
        sysroot = sysroot.replace("\\", "/") if sysroot is not None else None
        self.sysroot_flag = "--sysroot {}".format(sysroot) if sysroot else None

        self.configure_args = self._default_configure_shared_flags() + \
                              self._default_configure_install_flags() + \
                              self._get_triplets()
        self.autoreconf_args = self._default_autoreconf_flags()
        self.make_args = []
        # Apple stuff
        is_cross_building_osx = (is_cross_building
                                 and conanfile.settings_build.get_safe('os') == "Macos"
                                 and is_apple_os(conanfile))
        min_flag, arch_flag, isysroot_flag = resolve_apple_flags(conanfile,
                                                                 is_cross_building=is_cross_building_osx)
        # https://man.archlinux.org/man/clang.1.en#Target_Selection_Options
        self.apple_arch_flag = arch_flag
        # -isysroot makes all includes for your library relative to the build directory
        self.apple_isysroot_flag = isysroot_flag
        self.apple_min_version_flag = min_flag

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
        self.generate_args()
        VCVars(self._conanfile).generate(scope=scope)

    def _default_configure_shared_flags(self):
        args = []
        # Just add these flags if there's a shared option defined (never add to exe's)
        try:
            if self._conanfile.package_type is PackageType.SHARED:
                args.extend(["--enable-shared", "--disable-static"])
            elif self._conanfile.package_type is PackageType.STATIC:
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

    @staticmethod
    def _default_autoreconf_flags():
        return ["--force", "--install"]

    def _get_triplets(self):
        triplets = []
        for flag, value in (("--host=", self._host), ("--build=", self._build),
                            ("--target=", self._target)):
            if value:
                triplets.append(f'{flag}{value}')
        return triplets

    def update_configure_args(self, updated_flags):
        """
        Helper to update/prune flags from ``self.configure_args``.

        :param updated_flags: ``dict`` with arguments as keys and their argument values.
                              Notice that if argument value is ``None``, this one will be pruned.
        """
        self._update_flags("configure_args", updated_flags)

    def update_make_args(self, updated_flags):
        """
        Helper to update/prune arguments from ``self.make_args``.

        :param updated_flags: ``dict`` with arguments as keys and their argument values.
                              Notice that if argument value is ``None``, this one will be pruned.
        """
        self._update_flags("make_args", updated_flags)

    def update_autoreconf_args(self, updated_flags):
        """
        Helper to update/prune arguments from ``self.autoreconf_args``.

        :param updated_flags: ``dict`` with arguments as keys and their argument values.
                              Notice that if argument value is ``None``, this one will be pruned.
        """
        self._update_flags("autoreconf_args", updated_flags)

    # FIXME: Remove all these update_xxxx whenever xxxx_args are dicts or new ones replace them
    def _update_flags(self, attr_name, updated_flags):

        def _list_to_dict(flags):
            ret = {}
            for flag in flags:
                # Only splitting if "=" is there
                option = flag.split("=", 1)
                if len(option) == 2:
                    ret[option[0]] = option[1]
                else:
                    ret[option[0]] = ""
            return ret

        def _dict_to_list(flags):
            return [f"{k}={v}" if v else k for k, v in flags.items() if v is not None]

        self_args = getattr(self, attr_name)
        # FIXME: if xxxxx_args -> dict-type at some point, all these lines could be removed
        options = _list_to_dict(self_args)
        # Add/update/remove the current xxxxx_args with the new flags given
        options.update(updated_flags)
        # Update the current ones
        setattr(self, attr_name, _dict_to_list(options))

    def generate_args(self):
        args = {"configure_args": cmd_args_to_string(self.configure_args),
                "make_args":  cmd_args_to_string(self.make_args),
                "autoreconf_args": cmd_args_to_string(self.autoreconf_args)}
        save_toolchain_args(args, namespace=self._namespace)
