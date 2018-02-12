from conans.model import Generator
from conans.paths import BUILD_INFO_COMPILER_ARGS
from conans.client.build.compiler_flags import (architecture_flag, sysroot_flag,
                                                format_defines, format_include_paths,
                                                format_library_paths, format_libraries,
                                                build_type_flag, build_type_define, libcxx_flag,
                                                libcxx_define, rpath_flags)


class CompilerArgsGenerator(Generator):

    @property
    def filename(self):
        return BUILD_INFO_COMPILER_ARGS

    @property
    def compiler(self):
        return self.conanfile.settings.get_safe("compiler")

    @property
    def content(self):
        """With gcc_flags you can invoke gcc like that:
        $ gcc main.c @conanbuildinfo.args -o main
        """
        flags = []
        flags.extend(format_defines(self._deps_build_info.defines, compiler=self.compiler))
        flags.extend(format_include_paths(self._deps_build_info.include_paths, compiler=self.compiler))

        flags.extend(rpath_flags(self.compiler, self._deps_build_info.lib_paths))  # rpaths

        flags.extend(format_library_paths(self._deps_build_info.lib_paths, compiler=self.compiler))
        flags.extend(format_libraries(self._deps_build_info.libs, compiler=self.compiler))
        flags.extend(self._deps_build_info.cppflags)
        flags.extend(self._deps_build_info.cflags)
        flags.extend(self._deps_build_info.sharedlinkflags)
        flags.extend(self._deps_build_info.exelinkflags)
        flags.extend(self._libcxx_flags())
        sysrf = sysroot_flag(self._deps_build_info.sysroot, compiler=self.compiler)
        if sysrf:
            flags.append(sysrf)
        arch_flag = architecture_flag(arch=self.conanfile.settings.get_safe("arch"), compiler=self.compiler)
        if arch_flag:
            flags.append(arch_flag)

        build_type = self.conanfile.settings.get_safe("build_type")
        btf = build_type_flag(compiler=self.compiler, build_type=build_type)
        if btf:
            flags.append(btf)
        btd = build_type_define(build_type=build_type)
        if btd:
            flags.append(format_defines([btd], self.compiler)[0])

        return " ".join(flag for flag in flags if flag)

    def _libcxx_flags(self):
        libcxx = self.conanfile.settings.get_safe("compiler.libcxx")
        compiler = self.conanfile.settings.get_safe("compiler")

        lib_flags = []
        if libcxx:
            stdlib_define = libcxx_define(compiler=compiler, libcxx=libcxx)
            lib_flags.extend(format_defines([stdlib_define], compiler=compiler))
            cxxf = libcxx_flag(compiler=compiler, libcxx=libcxx)
            if cxxf:
                lib_flags.append(cxxf)

        return lib_flags
