from conans.client.build.compiler_flags import (architecture_flag, build_type_define,
                                                build_type_flags, format_defines,
                                                format_include_paths, format_libraries,
                                                format_library_paths, libcxx_define, libcxx_flag,
                                                rpath_flags, sysroot_flag,
                                                visual_linker_option_separator, visual_runtime,
                                                format_frameworks, format_framework_paths)
from conans.client.build.cppstd_flags import cppstd_flag_new as cppstd_flag
from conans.client.tools.oss import get_build_os_arch
from conans.model import Generator
from conans.paths import BUILD_INFO_COMPILER_ARGS


class CompilerArgsGenerator(Generator):

    @property
    def filename(self):
        return BUILD_INFO_COMPILER_ARGS

    @property
    def compiler(self):
        return self.conanfile.settings.get_safe("compiler")

    @property
    def _settings(self):
        settings = self.conanfile.settings.copy()
        if self.settings.get_safe("compiler"):
            settings.compiler = self.compiler
        return settings

    @property
    def content(self):
        """With compiler_args you can invoke your compiler:
        $ gcc main.c @conanbuildinfo.args -o main
        $ clang main.c @conanbuildinfo.args -o main
        $ cl /EHsc main.c @conanbuildinfo.args
        """

        flags = []
        flags.extend(format_defines(self._deps_build_info.defines))
        flags.extend(format_include_paths(self._deps_build_info.include_paths,
                                          self._settings))

        flags.extend(self._deps_build_info.cxxflags)
        flags.extend(self._deps_build_info.cflags)

        arch_flag = architecture_flag(self._settings)
        if arch_flag:
            flags.append(arch_flag)

        build_type = self.conanfile.settings.get_safe("build_type")
        btfs = build_type_flags(self._settings)
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

        os_build, _ = get_build_os_arch(self.conanfile)
        if not hasattr(self.conanfile, 'settings_build'):
            os_build = os_build or self.conanfile.settings.get_safe("os")

        flags.extend(rpath_flags(self._settings, os_build, self._deps_build_info.lib_paths))
        flags.extend(format_library_paths(self._deps_build_info.lib_paths, self._settings))
        flags.extend(format_libraries(self._deps_build_info.libs, self._settings))
        flags.extend(format_libraries(self._deps_build_info.system_libs, self._settings))

        flags.extend(self._deps_build_info.sharedlinkflags)
        flags.extend(self._deps_build_info.exelinkflags)
        flags.extend(self._libcxx_flags())
        flags.extend(format_frameworks(self._deps_build_info.frameworks, self._settings))
        flags.extend(format_framework_paths(self._deps_build_info.framework_paths,
                                            self._settings))
        flags.append(cppstd_flag(self._settings))
        sysrf = sysroot_flag(self._deps_build_info.sysroot, self._settings)
        if sysrf:
            flags.append(sysrf)

        return " ".join(flag for flag in flags if flag)

    def _libcxx_flags(self):
        libcxx = self._settings.get_safe("compiler.libcxx")

        lib_flags = []
        if libcxx:
            stdlib_define = libcxx_define(self._settings)
            lib_flags.extend(format_defines([stdlib_define]))
            cxxf = libcxx_flag(self._settings)
            if cxxf:
                lib_flags.append(cxxf)

        return lib_flags
