


class AutotoolsToolchain(object):
    def __init__(self):
        self.defines = self._configure_defines()
        # Only c++ flags [-stdlib, -library], will go to CXXFLAGS
        self.cxx_flags = self._configure_cxx_flags()
        self.cflags = self._configure_flags()
        # cpp standard
        self.cppstd_flag = cppstd_flag(conanfile.settings)
        # Not -L flags, ["-m64" "-m32"]
        self.link_flags = self._configure_link_flags()  # TEST!
        # Precalculate -fPIC
        self.fpic = self._configure_fpic()

    def _configure_fpic(self):
        if not str(self._os).startswith("Windows"):
            fpic = self._conanfile.options.get_safe("fPIC")
            if fpic is not None:
                shared = self._conanfile.options.get_safe("shared")
                return True if (fpic or shared) else None

    def _configure_link_flags(self):
        """Not the -L"""
        ret = list(self._deps_cpp_info.sharedlinkflags)
        ret.extend(list(self._deps_cpp_info.exelinkflags))
        ret.extend(format_frameworks(self._deps_cpp_info.frameworks, self._conanfile.settings))
        ret.extend(format_framework_paths(self._deps_cpp_info.framework_paths,
                                          self._conanfile.settings))
        arch_flag = architecture_flag(self._conanfile.settings)
        if arch_flag:
            ret.append(arch_flag)

        sysf = sysroot_flag(self._deps_cpp_info.sysroot, self._conanfile.settings,
                            win_bash=self._win_bash,
                            subsystem=self.subsystem)
        if sysf:
            ret.append(sysf)

        if self._include_rpath_flags:
            os_build, _ = get_build_os_arch(self._conanfile)
            if not hasattr(self._conanfile, 'settings_build'):
                os_build = os_build or self._os
            ret.extend(rpath_flags(self._conanfile.settings, os_build,
                                   self._deps_cpp_info.lib_paths))

        return ret
    def _configure_defines(self):
        # Debug definition for GCC
        btf = build_type_define(build_type=self._build_type)
        if btf:
            ret.append(btf)

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
        srf = sysroot_flag(self._deps_cpp_info.sysroot,
                           self._conanfile.settings,
                           win_bash=self._win_bash,
                           subsystem=self.subsystem)
        if srf:
            ret.append(srf)
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
