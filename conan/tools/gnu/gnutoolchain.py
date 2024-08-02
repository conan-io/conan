import os

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
from conans.errors import ConanException
from conans.model.pkg_type import PackageType


class GnuToolchain:
    """
    GnuToolchain generator.

    Note: it's based on legacy AutotoolsToolchain but with a more modern and usable UX
    """
    script_name = "conangnutoolchain"

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
        # Extra environment definitions
        self.extra_env = Environment()
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

        # Host/Build triplets
        self.triplets_info = {
            "host": {"triplet": self._conanfile.conf.get("tools.gnu:host_triplet")},
            "build": {"triplet": self._conanfile.conf.get("tools.gnu:build_triplet")}
        }
        self._is_cross_building = cross_building(self._conanfile)
        if self._is_cross_building:
            compiler = self._conanfile.settings.get_safe("compiler")
            # Host triplet
            if not self.triplets_info["host"]["triplet"]:
                os_host = conanfile.settings.get_safe("os")
                arch_host = conanfile.settings.get_safe("arch")
                self.triplets_info["host"] = _get_gnu_triplet(os_host, arch_host, compiler=compiler)
            # Build triplet
            if not self.triplets_info["build"]["triplet"]:
                os_build = conanfile.settings_build.get_safe('os')
                arch_build = conanfile.settings_build.get_safe('arch')
                self.triplets_info["build"] = _get_gnu_triplet(os_build, arch_build, compiler=compiler)

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
        is_cross_building_osx = (self._is_cross_building
                                 and conanfile.settings_build.get_safe('os') == "Macos"
                                 and is_apple_os(conanfile))
        min_flag, arch_flag, isysroot_flag = (
            resolve_apple_flags(conanfile, is_cross_building=is_cross_building_osx)
        )
        # https://man.archlinux.org/man/clang.1.en#Target_Selection_Options
        self.apple_arch_flag = arch_flag
        # -isysroot makes all includes for your library relative to the build directory
        self.apple_isysroot_flag = isysroot_flag
        self.apple_min_version_flag = min_flag
        # Default initial environment flags
        self._initialize_default_extra_env()

    def yes_no(self, option_name, default=None, negated=False):
        """
        Simple wrapper to return "yes" or "no" depending on whether option_name is
        evaluated as True or False.

        :param option_name: option name.
        :param default: Default value to return.
        :param negated: Negates the option value if True.
        :return: "yes" or "no" depending on whether option_name is True or False.
        """
        option_value = bool(self._conanfile.options.get_safe(option_name, default=default))
        option_value = not option_value if negated else option_value
        return "yes" if option_value else "no"

    def _resolve_android_cross_compilation(self):
        # Issue related: https://github.com/conan-io/conan/issues/13443
        ret = {}
        if not self._is_cross_building or not self._conanfile.settings.get_safe("os") == "Android":
            return ret

        ndk_path = self._conanfile.conf.get("tools.android:ndk_path", check_type=str)
        if not ndk_path:
            raise ConanException("You must provide a NDK path. Use 'tools.android:ndk_path' "
                                 "configuration field.")

        if ndk_path:
            arch = self._conanfile.settings.get_safe("arch")
            os_build = self._conanfile.settings_build.get_safe("os")
            ndk_os_folder = {
                'Macos': 'darwin',
                'iOS': 'darwin',
                'watchOS': 'darwin',
                'tvOS': 'darwin',
                'visionOS': 'darwin',
                'FreeBSD': 'linux',
                'Linux': 'linux',
                'Windows': 'windows',
                'WindowsCE': 'windows',
                'WindowsStore': 'windows'
            }.get(os_build, "linux")
            ndk_bin = os.path.join(ndk_path, "toolchains", "llvm", "prebuilt",
                                   f"{ndk_os_folder}-x86_64", "bin")
            android_api_level = self._conanfile.settings.get_safe("os.api_level")
            android_target = {'armv7': 'armv7a-linux-androideabi',
                              'armv8': 'aarch64-linux-android',
                              'x86': 'i686-linux-android',
                              'x86_64': 'x86_64-linux-android'}.get(arch)
            os_build = self._conanfile.settings_build.get_safe('os')
            ext = ".cmd" if os_build == "Windows" else ""
            ret = {
                "CC": os.path.join(ndk_bin, f"{android_target}{android_api_level}-clang{ext}"),
                "CXX": os.path.join(ndk_bin, f"{android_target}{android_api_level}-clang++{ext}"),
                "LD": os.path.join(ndk_bin, "ld"),
                "STRIP": os.path.join(ndk_bin, "llvm-strip"),
                "RANLIB": os.path.join(ndk_bin, "llvm-ranlib"),
                "AS": os.path.join(ndk_bin, f"{android_target}{android_api_level}-clang{ext}"),
                "AR": os.path.join(ndk_bin, "llvm-ar"),
            }
            # Overriding host triplet
            self.triplets_info["host"]["triplet"] = android_target
        return ret

    def _resolve_compilers_mapping_variables(self):
        ret = {}
        # Configuration map
        compilers_mapping = {"c": "CC", "cpp": "CXX", "cuda": "NVCC", "fortran": "FC",
                             "rc": "RC", "nm": "NM", "ranlib": "RANLIB",
                             "objdump": "OBJDUMP", "strip": "STRIP"}
        # Compiler definitions by conf
        compilers_by_conf = self._conanfile.conf.get("tools.build:compiler_executables",
                                                     default={}, check_type=dict)
        if compilers_by_conf:
            for comp, env_var in compilers_mapping.items():
                if comp in compilers_by_conf:
                    compiler = compilers_by_conf[comp]
                    # https://github.com/conan-io/conan/issues/13780
                    compiler = unix_path(self._conanfile, compiler)
                    ret[env_var] = compiler  # User/tools ones have precedence
        # Issue related: https://github.com/conan-io/conan/issues/15486
        if self._is_cross_building and self._conanfile.conf_build:
            compilers_build_mapping = (
                self._conanfile.conf_build.get("tools.build:compiler_executables", default={},
                                               check_type=dict)
            )
            if "c" in compilers_build_mapping:
                ret["CC_FOR_BUILD"] = compilers_build_mapping["c"]
            if "cpp" in compilers_build_mapping:
                ret["CXX_FOR_BUILD"] = compilers_build_mapping["cpp"]
        return ret

    def _initialize_default_extra_env(self):
        """Initialize the default environment variables."""
        # If it's an Android cross-compilation
        extra_env_vars = self._resolve_android_cross_compilation()
        if not extra_env_vars:
            # Normally, these are the most common default flags used by MSVC in Windows
            if is_msvc(self._conanfile):
                extra_env_vars = {"CC": "cl -nologo",
                                  "CXX": "cl -nologo",
                                  "LD": "link -nologo",
                                  "AR": "lib",
                                  "NM": "dumpbin -symbols",
                                  "OBJDUMP": ":",
                                  "RANLIB": ":",
                                  "STRIP": ":"}
            extra_env_vars.update(self._resolve_compilers_mapping_variables())

        # Update the extra_env attribute with all the compiler values
        for env_var, env_value in extra_env_vars.items():
            self.extra_env.define(env_var, env_value)

    def _get_msvc_runtime_flag(self):
        flag = msvc_runtime_flag(self._conanfile)
        return f"-{flag}" if flag else ""

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
        configure_install_flags = {"--prefix": self._prefix}
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
        for context, info in self.triplets_info.items():
            if info.get("triplet") is not None:
                triplets[f"--{context}"] = info["triplet"]
        return triplets

    @property
    def _environment(self):
        env = Environment()
        # Flags and defines
        env.append("CPPFLAGS", ["-D{}".format(d) for d in self.defines])
        env.append("CXXFLAGS", self.cxxflags)
        env.append("CFLAGS", self.cflags)
        env.append("LDFLAGS", self.ldflags)
        env.prepend_path("PKG_CONFIG_PATH", self._conanfile.generators_folder)
        # Let's compose with user extra env variables defined (user ones have precedence)
        return self.extra_env.compose_env(env)

    def generate(self):
        check_duplicated_generator(self, self._conanfile)
        # Composing both environments. User extra_env definitions has precedence
        env_vars = self._environment.vars(self._conanfile)
        env_vars.save_script(GnuToolchain.script_name)
        # Converts all the arguments into strings
        args = {
            "configure_args": cmd_args_to_string(self._dict_to_list(self.configure_args)),
            "make_args": cmd_args_to_string(self._dict_to_list(self.make_args)),
            "autoreconf_args": cmd_args_to_string(self._dict_to_list(self.autoreconf_args))
        }
        save_toolchain_args(args, namespace=self._namespace)
        VCVars(self._conanfile).generate()
