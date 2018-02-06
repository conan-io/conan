from conans.model import Generator
from conans.paths import BUILD_INFO_GCC
from conans.client.build.compiler_flags import architecture_flags, libcxx_flags, build_type_flags, sysroot_flags,\
    format_defines, format_include_paths, format_library_paths, format_libraries
import platform


class GCCGenerator(Generator):
    @property
    def filename(self):
        return BUILD_INFO_GCC

    @property
    def content(self):
        """With gcc_flags you can invoke gcc like that:
        $ gcc main.c @conanbuildinfo.gcc -o main
        """
        flags = []
        flags.extend(format_defines(self._deps_build_info.defines))
        flags.extend(format_include_paths(self._deps_build_info.include_paths, compiler='gcc'))
        rpath_separator = "," if platform.system() == "Darwin" else "="
        flags.extend(['-Wl,-rpath%s"%s"' % (rpath_separator, x.replace("\\", "/")) 
                      for x in self._deps_build_info.lib_paths])  # rpaths
        flags.extend(format_library_paths(self._deps_build_info.lib_paths, compiler='gcc'))
        flags.extend(format_libraries(self._deps_build_info.libs, compiler='gcc'))
        flags.extend(self._deps_build_info.cppflags)
        flags.extend(self._deps_build_info.cflags)
        flags.extend(self._deps_build_info.sharedlinkflags)
        flags.extend(self._deps_build_info.exelinkflags)
        flags.extend(self._libcxx_flags())
        flags.extend(sysroot_flags(self._deps_build_info.sysroot, compiler='gcc').cflags)
        arch = self.conanfile.settings.get_safe("arch")
        flags.append(' '.join(architecture_flags(arch=arch).cflags))

        build_type = self.conanfile.settings.get_safe("build_type")
        bt_flags = build_type_flags(compiler='gcc', build_type=build_type)
        flags.extend(bt_flags.cflags)
        flags.extend(format_defines(bt_flags.defines))

        return " ".join(flags)

    def _libcxx_flags(self):
        libcxx = self.conanfile.settings.get_safe("compiler.libcxx")
        compiler = self.conanfile.settings.get_safe("compiler")

        lib_flags = []
        if libcxx:
            stdlib_flags = libcxx_flags(compiler=compiler, libcxx=libcxx)
            lib_flags.extend(format_defines(stdlib_flags.defines))
            lib_flags.extend(stdlib_flags.cxxflags)

        return lib_flags

