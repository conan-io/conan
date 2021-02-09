from conan.tools.env import Environment


class AutotoolsToolchain(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        """
        self.cxx_flags = self._configure_cxx_flags()
        self.cflags = self._configure_flags()
        # cpp standard
        # self.cppstd_flag = cppstd_flag(conanfile.settings)
        # Not -L flags, ["-m64" "-m32"]
        self.link_flags = self._configure_link_flags()  # TEST!
        # Precalculate -fPIC
        self.fpic = self._configure_fpic()"""
        build_type = self._conanfile.settings.get_safe("build_type")

        # defines
        self.ndebug = None
        if build_type in ['Release', 'RelWithDebInfo', 'MinSizeRel']:
            self.ndebug = "NDEBUG"
        self.gcc_cxx11_abi = self._cxx11_abi_define()
        self.defines = []

        # cxxflags
        self.cxxflags = []
        self.libcxx = self._libcxx()

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

    def generate(self):
        env = Environment()
        # defines
        if self.ndebug and self.ndebug not in self.defines:
            self.defines.append(self.ndebug)
        if self.gcc_cxx11_abi and self.gcc_cxx11_abi not in self.defines:
            self.defines.append(self.gcc_cxx11_abi)
        env["CPPFLAGS"].append(["-D{}".format(d) for d in self.defines])

        # cxxflags
        if self.libcxx and self.libcxx not in self.cxxflags:
            self.cxxflags.append(self.libcxx)
        env["CXXFLAGS"].append(self.cxxflags)

        # env["LDFLAGS"].define(self.ldflags)
        env.save_sh("autotools.sh")
        env.save_bat("autotools.bat")

    def _configure_fpic(self):
        tmp_compilation_flags.append(pic_flag(self._conanfile.settings))

        if not str(self._os).startswith("Windows"):
            fpic = self._conanfile.options.get_safe("fPIC")
            if fpic is not None:
                shared = self._conanfile.options.get_safe("shared")
                return True if (fpic or shared) else None

    def _configure_link_flags(self):
        """Not the -L"""
        arch_flag = architecture_flag(self._conanfile.settings)

        if self._include_rpath_flags:
            os_build, _ = get_build_os_arch(self._conanfile)
            if not hasattr(self._conanfile, 'settings_build'):
                os_build = os_build or self._os
            ret.extend(rpath_flags(self._conanfile.settings, os_build,
                                   self._deps_cpp_info.lib_paths))

    def _configure_flags(self):
        arch_flag = architecture_flag(self._conanfile.settings)
        btfs = build_type_flags(self._conanfile.settings)
        if self._compiler_runtime:
            ret.append("-%s" % self._compiler_runtime)
