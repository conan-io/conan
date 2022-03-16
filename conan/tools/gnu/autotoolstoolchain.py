from conan.tools._check_build_profile import check_using_build_profile
from conan.tools._compilers import architecture_flag, build_type_flags, cppstd_flag, \
    build_type_link_flags
from conan.tools.apple.apple import apple_min_version_flag, to_apple_arch, \
    apple_sdk_path, is_apple_os
from conan.tools.build.cross_building import cross_building, get_cross_building_settings
from conan.tools.env import Environment
from conan.tools.files.files import save_toolchain_args
from conan.tools.gnu.get_gnu_triplet import _get_gnu_triplet
from conan.tools.microsoft import VCVars, is_msvc
from conans.model.conf import Conf
from conans.tools import args_to_string


class _AutotoolFlags:

    def __init__(self, conanfile, is_apple_cross_building=False):
        self._conanfile = conanfile
        self._is_apple_cross_building = is_apple_cross_building
        # Load all the predefined Conan C, CXX, etc. flags for CMakeToolchain
        self._conan_conf = Conf()
        self._process_conan_flags()

    def _get_cxx11_abi_define(self):
        # https://gcc.gnu.org/onlinedocs/libstdc++/manual/using_dual_abi.html
        # The default is libstdc++11, only specify the contrary '_GLIBCXX_USE_CXX11_ABI=0'
        settings = self._conanfile.settings
        libcxx = settings.get_safe("compiler.libcxx")
        if not libcxx:
            return

        compiler = settings.get_safe("compiler.base") or settings.get_safe("compiler")
        if compiler in ['clang', 'apple-clang', 'gcc']:
            if libcxx == 'libstdc++':
                return '_GLIBCXX_USE_CXX11_ABI=0'
            elif libcxx == "libstdc++11" and self._conanfile.conf.get("tools.gnu:define_libcxx11_abi",
                                                                      check_type=bool):
                return '_GLIBCXX_USE_CXX11_ABI=1'

    def _get_msvc_runtime_flag(self):
        msvc_runtime_flag = None
        if self._conanfile.settings.get_safe("compiler") == "msvc":
            runtime_type = self._conanfile.settings.get_safe("compiler.runtime_type")
            if runtime_type == "Release":
                values = {"static": "MT", "dynamic": "MD"}
            else:
                values = {"static": "MTd", "dynamic": "MDd"}
            runtime = values.get(self._conanfile.settings.get_safe("compiler.runtime"))
            if runtime:
                msvc_runtime_flag = "-{}".format(runtime)
        elif self._conanfile.settings.get_safe("compiler") == "Visual Studio":
            runtime = self._conanfile.settings.get_safe("compiler.runtime")
            if runtime:
                msvc_runtime_flag = "-{}".format(runtime)

        return msvc_runtime_flag

    def _get_libcxx_flag(self):
        settings = self._conanfile.settings
        libcxx = settings.get_safe("compiler.libcxx")
        if not libcxx:
            return

        compiler = settings.get_safe("compiler.base") or settings.get_safe("compiler")

        if compiler in ['clang', 'apple-clang']:
            if libcxx in ['libstdc++', 'libstdc++11']:
                return '-stdlib=libstdc++'
            elif libcxx == 'libc++':
                return '-stdlib=libc++'
        elif compiler == 'sun-cc':
            return ({"libCstd": "-library=Cstd",
                     "libstdcxx": "-library=stdcxx4",
                     "libstlport": "-library=stlport4",
                     "libstdc++": "-library=stdcpp"}.get(libcxx))
        elif compiler == "qcc":
            return "-Y _%s" % str(libcxx)

    def _get_apple_flags(self):
        os_ = self._conanfile.settings.get_safe("os")
        if not is_apple_os(os_):
            return []

        apple_min_vflag = apple_min_version_flag(self._conanfile)
        apple_arch_flag = apple_isysroot_flag = None

        if self._is_apple_cross_building:
            sdk_path = apple_sdk_path(self._conanfile)
            apple_arch = to_apple_arch(self._conanfile.settings.get_safe("arch"))
            # https://man.archlinux.org/man/clang.1.en#Target_Selection_Options
            apple_arch_flag = "-arch {}".format(apple_arch) if apple_arch else None
            # -isysroot makes all includes for your library relative to the build directory
            apple_isysroot_flag = "-isysroot {}".format(sdk_path) if sdk_path else None

        return [apple_isysroot_flag, apple_arch_flag, apple_min_vflag]

    def _process_conan_flags(self):
        """Calculating all the flags predefined by Conan"""
        # TODO: compiler.runtime for Visual studio?
        # Defines
        gcc_cxx11_abi = self._get_cxx11_abi_define()
        ndebug = None
        if self._conanfile.settings.get_safe("build_type") in ['Release', 'RelWithDebInfo', 'MinSizeRel']:
            ndebug = "NDEBUG"

        # TODO: This is also covering compilers like Visual Studio, necessary to test it (&remove?)
        btype_flags = build_type_flags(self._conanfile.settings)
        btype_lflags = build_type_link_flags(self._conanfile.settings)

        cppstd = cppstd_flag(self._conanfile.settings)
        arch_flag = architecture_flag(self._conanfile.settings)
        libcxx = self._get_libcxx_flag()
        fpic = "-fPIC" if self._conanfile.options.get_safe("fPIC") else ""
        msvc_runtime_flag = self._get_msvc_runtime_flag()
        apple_flags = self._get_apple_flags()

        # Creating all the flags variables
        cxxflags = [libcxx, cppstd, arch_flag, fpic, msvc_runtime_flag] + btype_flags + apple_flags
        cflags = [arch_flag, fpic, msvc_runtime_flag] + btype_flags + apple_flags
        ldflags = [arch_flag] + btype_lflags + apple_flags
        cppflags = [ndebug, gcc_cxx11_abi]
        # Saving them into the internal Conan conf
        self._conan_conf.define("tools.build:cxxflags", cxxflags)
        self._conan_conf.define("tools.build:cflags", cflags)
        self._conan_conf.define("tools.build:ldflags", ldflags)
        self._conan_conf.define("tools.build:cppflags", cppflags)

    @staticmethod
    def _filter_empty_list_fields(v):
        return list(filter(bool, v))

    def context(self):
        # Now, it's time to update the predefined flags with [conf] ones injected by the user
        self._conan_conf.compose_conf(self._conanfile.conf)
        cxxflags = self._conan_conf.get("tools.build:cxxflags", default=[], check_type=list)
        cflags = self._conan_conf.get("tools.build:cflags", default=[], check_type=list)
        cppflags = self._conan_conf.get("tools.build:cppflags", default=[], check_type=list)
        ldflags = self._conan_conf.get("tools.build:ldflags", default=[], check_type=list)
        return {
            "cxxflags": self._filter_empty_list_fields(cxxflags),
            "cflags": self._filter_empty_list_fields(cflags),
            "cppflags": ["-D{}".format(d) for d in self._filter_empty_list_fields(cppflags)],
            "ldflags": self._filter_empty_list_fields(ldflags),
        }


class AutotoolsToolchain:

    def __init__(self, conanfile, namespace=None):
        self._conanfile = conanfile
        self._namespace = namespace

        self.configure_args = []
        self.make_args = []
        self.default_configure_install_args = True

        # Cross build
        self._host = None
        self._build = None
        self._target = None

        os_build = None
        is_cross_building = cross_building(self._conanfile)
        if is_cross_building:
            os_build, arch_build, os_host, arch_host = get_cross_building_settings(self._conanfile)
            compiler = self._conanfile.settings.get_safe("compiler")
            self._host = _get_gnu_triplet(os_host, arch_host, compiler=compiler)
            self._build = _get_gnu_triplet(os_build, arch_build, compiler=compiler)

        check_using_build_profile(self._conanfile)
        # Get all the flags
        is_apple_cross_building = all([is_cross_building, os_build == "Macos"])
        self._autotool_flags = _AutotoolFlags(conanfile, is_apple_cross_building=is_apple_cross_building)

    def environment(self):
        env = Environment()

        if is_msvc(self._conanfile):
            env.define("CXX", "cl")
            env.define("CC", "cl")

        flags = self._autotool_flags.context()
        env.append("CPPFLAGS", flags["cppflags"])
        env.append("CXXFLAGS", flags["cxxflags"])
        env.append("CFLAGS", flags["cflags"])
        env.append("LDFLAGS", flags["ldflags"])
        return env

    def vars(self):
        return self.environment().vars(self._conanfile, scope="build")

    def generate(self, env=None, scope="build"):
        env = env or self.environment()
        env = env.vars(self._conanfile, scope=scope)
        env.save_script("conanautotoolstoolchain")
        self.generate_args()
        VCVars(self._conanfile).generate(scope=scope)

    def generate_args(self):
        configure_args = []
        configure_args.extend(self.configure_args)

        if self.default_configure_install_args and self._conanfile.package_folder:
            def _get_cpp_info_value(name):
                # Why not taking cpp.build? because this variables are used by the "cmake install"
                # that correspond to the package folder (even if the root is the build directory)
                elements = getattr(self._conanfile.cpp.package, name)
                return elements[0] if elements else None

            # If someone want arguments but not the defaults can pass them in args manually
            configure_args.extend(
                    ['--prefix=%s' % self._conanfile.package_folder.replace("\\", "/"),
                     "--bindir=${prefix}/%s" % _get_cpp_info_value("bindirs"),
                     "--sbindir=${prefix}/%s" % _get_cpp_info_value("bindirs"),
                     "--libdir=${prefix}/%s" % _get_cpp_info_value("libdirs"),
                     "--includedir=${prefix}/%s" % _get_cpp_info_value("includedirs"),
                     "--oldincludedir=${prefix}/%s" % _get_cpp_info_value("includedirs"),
                     "--datarootdir=${prefix}/%s" % _get_cpp_info_value("resdirs")])
        user_args_str = args_to_string(self.configure_args)
        for flag, var in (("host", self._host), ("build", self._build), ("target", self._target)):
            if var and flag not in user_args_str:
                configure_args.append('--{}={}'.format(flag, var))

        args = {"configure_args": args_to_string(configure_args),
                "make_args":  args_to_string(self.make_args)}

        save_toolchain_args(args, namespace=self._namespace)
