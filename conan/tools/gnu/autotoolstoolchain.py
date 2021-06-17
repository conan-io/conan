import json

from conan.tools import CONAN_TOOLCHAIN_ARGS_FILE
from conan.tools._compilers import architecture_flag, build_type_flags
from conan.tools.apple.apple import apple_min_version_flag, to_apple_arch, \
    apple_sdk_path
from conan.tools.env import Environment
from conan.tools.files import save
from conan.tools.cross_building import cross_building, get_cross_building_settings
from conan.tools.gnu.get_cppstd import cppstd_flag
from conan.tools.gnu.get_gnu_triplet import _get_gnu_triplet


class AutotoolsToolchain:
    def __init__(self, conanfile):
        self._conanfile = conanfile
        build_type = self._conanfile.settings.get_safe("build_type")

        # TODO: compiler.runtime for Visual studio?
        # defines
        self.ndebug = None
        if build_type in ['Release', 'RelWithDebInfo', 'MinSizeRel']:
            self.ndebug = "NDEBUG"
        self.gcc_cxx11_abi = self._cxx11_abi_define()
        self.defines = []

        # cxxflags, cflags
        self.cxxflags = []
        self.cflags = []
        self.ldflags = []
        self.libcxx = self._libcxx()
        self.fpic = self._conanfile.options.get_safe("fPIC")

        self.cppstd = cppstd_flag(self._conanfile.settings)
        self.arch_flag = architecture_flag(self._conanfile.settings)
        # TODO: This is also covering compilers like Visual Studio, necessary to test it (&remove?)
        self.build_type_flags = build_type_flags(self._conanfile.settings)

        # Cross build
        self._host = None
        self._build = None
        self._target = None

        self.apple_arch_flag = self.apple_isysroot_flag = None

        self.apple_min_version_flag = apple_min_version_flag(self._conanfile)
        if cross_building(self._conanfile):
            os_build, arch_build, os_host, arch_host = get_cross_building_settings(self._conanfile)
            self._host = _get_gnu_triplet(os_host, arch_host)
            self._build = _get_gnu_triplet(os_build, arch_build)

            # Apple Stuff
            if os_build == "Macos":
                sdk_path = apple_sdk_path(conanfile)
                apple_arch = to_apple_arch(self._conanfile.settings.get_safe("arch"))
                # https://man.archlinux.org/man/clang.1.en#Target_Selection_Options
                self.apple_arch_flag = "-arch {}".format(apple_arch) if apple_arch else None
                # -isysroot makes all includes for your library relative to the build directory
                self.apple_isysroot_flag = "-isysroot {}".format(sdk_path) if sdk_path else None

    def _cxx11_abi_define(self):
        # https://gcc.gnu.org/onlinedocs/libstdc++/manual/using_dual_abi.html
        # The default is libstdc++11, only specify the contrary '_GLIBCXX_USE_CXX11_ABI=0'
        settings = self._conanfile.settings
        libcxx = settings.get_safe("compiler.libcxx")
        if not libcxx:
            return

        compiler = settings.get_safe("compiler.base") or settings.get_safe("compiler")
        if compiler == "gcc":
            if libcxx == 'libstdc++':
                return '_GLIBCXX_USE_CXX11_ABI=0'

    def _libcxx(self):
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

    def environment(self):
        env = Environment()
        # defines
        if self.ndebug:
            self.defines.append(self.ndebug)
        if self.gcc_cxx11_abi:
            self.defines.append(self.gcc_cxx11_abi)

        if self.libcxx:
            self.cxxflags.append(self.libcxx)

        if self.cppstd:
            self.cxxflags.append(self.cppstd)

        if self.arch_flag:
            self.cxxflags.append(self.arch_flag)
            self.cflags.append(self.arch_flag)
            self.ldflags.append(self.arch_flag)

        if self.build_type_flags:
            self.cxxflags.extend(self.build_type_flags)
            self.cflags.extend(self.build_type_flags)

        if self.fpic:
            self.cxxflags.append("-fPIC")
            self.cflags.append("-fPIC")

        # FIXME: Previously these flags where checked if already present at env 'CFLAGS', 'CXXFLAGS'
        #        and 'self.cxxflags', 'self.cflags' before adding them
        for f in list(filter(bool, [self.apple_isysroot_flag,
                                    self.apple_arch_flag,
                                    self.apple_min_version_flag])):
            self.cxxflags.append(f)
            self.cflags.append(f)
            self.ldflags.append(f)

        env.append("CPPFLAGS", ["-D{}".format(d) for d in self.defines])
        env.append("CXXFLAGS", self.cxxflags)
        env.append("CFLAGS", self.cflags)
        env.append("LDFLAGS", self.ldflags)
        return env

    def generate(self, env=None):
        env = env or self.environment()
        env.save_script("conanautotoolstoolchain")
        self.generate_args()

    def generate_args(self):
        args = {"build": self._build,
                "host": self._host,
                "target": self._target}
        args = {k: v for k, v in args.items() if v is not None}
        save(self._conanfile, CONAN_TOOLCHAIN_ARGS_FILE, json.dumps(args))
