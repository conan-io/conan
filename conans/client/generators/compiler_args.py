from conans.client.build.cppstd_flags import cppstd_flag
from conans.model import Generator
from conans.paths import BUILD_INFO_COMPILER_ARGS
from conans.client.build.compiler_flags import (architecture_flag, sysroot_flag,
                                                format_defines, format_include_paths,
                                                format_library_paths, format_libraries,
                                                build_type_flags, build_type_define, libcxx_flag,
                                                libcxx_define, rpath_flags, visual_runtime,
                                                visual_linker_option_separator)


class CompilerArgsGenerator(Generator):

    @property
    def filename(self):
        return BUILD_INFO_COMPILER_ARGS

    @property
    def compiler(self):
        return self.conanfile.settings.get_safe("compiler")

    @property
    def content(self):
        """With compiler_args you can invoke your compiler:
        $ gcc main.c @conanbuildinfo.args -o main
        $ clang main.c @conanbuildinfo.args -o main
        $ cl /EHsc main.c @conanbuildinfo.args
        """
        flags = []
        flags.extend(format_defines(self._deps_build_info.defines))
        flags.extend(format_include_paths(self._deps_build_info.include_paths, compiler=self.compiler))

        flags.extend(self._deps_build_info.cppflags)
        flags.extend(self._deps_build_info.cflags)

        arch_flag = architecture_flag(arch=self.conanfile.settings.get_safe("arch"), compiler=self.compiler)
        if arch_flag:
            flags.append(arch_flag)

        build_type = self.conanfile.settings.get_safe("build_type")
        btfs = build_type_flags(compiler=self.compiler, build_type=build_type,
                                vs_toolset=self.conanfile.settings.get_safe("compiler.toolset"))
        if btfs:
            flags.extend(btfs)
        btd = build_type_define(build_type=build_type)
        if btd:
            flags.extend(format_defines([btd]))

        if self.compiler == "Visual Studio":
            runtime = visual_runtime(self.conanfile.settings.get_safe("compiler.runtime"))
            if runtime:
                flags.append(runtime)
            # Necessary in the "cl" invocation before specify the rest of linker flags
            flags.append(visual_linker_option_separator)

        the_os = (self.conanfile.settings.get_safe("os_build") or
                  self.conanfile.settings.get_safe("os"))
        flags.extend(rpath_flags(the_os, self.compiler, self._deps_build_info.lib_paths))
        flags.extend(format_library_paths(self._deps_build_info.lib_paths, compiler=self.compiler))
        flags.extend(format_libraries(self._deps_build_info.libs, compiler=self.compiler))
        flags.extend(self._deps_build_info.sharedlinkflags)
        flags.extend(self._deps_build_info.exelinkflags)
        flags.extend(self._libcxx_flags())
        flags.append(cppstd_flag(self.conanfile.settings.get_safe("compiler"),
                                 self.conanfile.settings.get_safe("compiler.version"),
                                 self.conanfile.settings.get_safe("cppstd")))
        sysrf = sysroot_flag(self._deps_build_info.sysroot, compiler=self.compiler)
        if sysrf:
            flags.append(sysrf)

        return " ".join(flag for flag in flags if flag)

    def _libcxx_flags(self):
        libcxx = self.conanfile.settings.get_safe("compiler.libcxx")
        compiler = self.conanfile.settings.get_safe("compiler")

        lib_flags = []
        if libcxx:
            stdlib_define = libcxx_define(compiler=compiler, libcxx=libcxx)
            lib_flags.extend(format_defines([stdlib_define]))
            cxxf = libcxx_flag(compiler=compiler, libcxx=libcxx)
            if cxxf:
                lib_flags.append(cxxf)

        return lib_flags
