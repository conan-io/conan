from conan.tools._compilers import architecture_flag, build_type_flags
from conan.tools.env import Environment
# FIXME: need to refactor this import and bring to conan.tools
from conans.client.build.cppstd_flags import cppstd_flag_new


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

        # FIXME: This needs to be imported here into conan.tools
        self.cppstd = cppstd_flag_new(self._conanfile.settings)
        self.arch_flag = architecture_flag(self._conanfile.settings)
        # TODO: This is also covering compilers like Visual Studio, necessary to test it (&remove?)
        self.build_type_flags = build_type_flags(self._conanfile.settings)

    def _rpaths_link(self):
        # TODO: Not implemented yet
        pass

    # TODO: Apple: tools.apple_deployment_target_flag,
    # TODO:  tools.XCRun(self._conanfile.settings).sdk_path
    # TODO: "-arch", tools.to_apple_arch(self._arch)

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

        env.append("CPPFLAGS", ["-D{}".format(d) for d in self.defines])
        env.append("CXXFLAGS", self.cxxflags)
        env.append("CFLAGS", self.cflags)
        env.append("LDFLAGS", self.ldflags)
        return env

    def generate(self):
        env = self.environment()
        env.save_sh("conanautotoolstoolchain.sh")
        env.save_bat("conanautotoolstoolchain.bat")
