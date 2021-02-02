from conan.tools.env import Environment


class AutotoolsToolchain(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        """self.defines = self._configure_defines()
        # Only c++ flags [-stdlib, -library], will go to CXXFLAGS
        self.cxx_flags = self._configure_cxx_flags()
        self.cflags = self._configure_flags()
        # cpp standard
        # self.cppstd_flag = cppstd_flag(conanfile.settings)
        # Not -L flags, ["-m64" "-m32"]
        self.link_flags = self._configure_link_flags()  # TEST!
        # Precalculate -fPIC
        self.fpic = self._configure_fpic()"""
        build_type = self._conanfile.settings.get_safe("build_type")
        self.defines = []
        if build_type in ['Release', 'RelWithDebInfo', 'MinSizeRel']:
            self.defines.append("NDEBUG")

    def generate(self):
        env = Environment()
        env["CPPFLAGS"].append(["-D{}".format(d) for d in self.defines])
        # env["LDFLAGS"].define(self.ldflags)
        env.save_sh("conantoolchain.sh")
        env.save_bat("conantoolchain.bat")

    def _configure_fpic(self):
        if not str(self._os).startswith("Windows"):
            fpic = self._conanfile.options.get_safe("fPIC")
            if fpic is not None:
                shared = self._conanfile.options.get_safe("shared")
                return True if (fpic or shared) else None

    def _configure_link_flags(self):
        """Not the -L"""
        arch_flag = architecture_flag(self._conanfile.settings)
        if arch_flag:
            ret.append(arch_flag)

        if self._include_rpath_flags:
            os_build, _ = get_build_os_arch(self._conanfile)
            if not hasattr(self._conanfile, 'settings_build'):
                os_build = os_build or self._os
            ret.extend(rpath_flags(self._conanfile.settings, os_build,
                                   self._deps_cpp_info.lib_paths))

        return ret

    def _configure_defines(self):
        # CXX11 ABI
        abif = libcxx_define(self._conanfile.settings)
        if abif:
            ret.append(abif)
        return ret

    def _configure_flags(self):
        arch_flag = architecture_flag(self._conanfile.settings)
        if arch_flag:
            ret.append(arch_flag)
        btfs = build_type_flags(self._conanfile.settings)
        if btfs:
            ret.extend(btfs)
        if self._compiler_runtime:
            ret.append("-%s" % self._compiler_runtime)

        return ret

    def _configure_cxx_flags(self):
        cxxf = libcxx_flag(self._conanfile.settings)
        if cxxf:
            ret.append(cxxf)
        return ret

    def _get_vars(self):
        tmp_compilation_flags = copy.copy(self.flags)
        if self.fpic:
            tmp_compilation_flags.append(pic_flag(self._conanfile.settings))
