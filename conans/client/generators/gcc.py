from conans.client.configure_build_environment import architecture_dict, stdlib_flags, \
    stdlib_defines
from conans.model import Generator
from conans.paths import BUILD_INFO_GCC
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
        flags.extend(["-D%s" % x for x in self._deps_build_info.defines])
        flags.extend(['-I"%s"' % x.replace("\\", "/") for x in self._deps_build_info.include_paths])
        rpath_separator = "," if platform.system() == "Darwin" else "="
        flags.extend(['-Wl,-rpath%s"%s"' % (rpath_separator, x.replace("\\", "/")) 
                      for x in self._deps_build_info.lib_paths]) # rpaths
        flags.extend(['-L"%s"' % x.replace("\\", "/") for x in self._deps_build_info.lib_paths])
        flags.extend(["-l%s" % x for x in self._deps_build_info.libs])
        flags.extend(self._deps_build_info.cppflags)
        flags.extend(self._deps_build_info.cflags)
        flags.extend(self._deps_build_info.sharedlinkflags)
        flags.extend(self._deps_build_info.exelinkflags)
        flags.extend(self._libcxx_flags())
        if self._deps_build_info.sysroot:
            flags.append("--sysroot=%s" % self._deps_build_info.sysroot)
        arch = self.conanfile.settings.get_safe("arch")
        flags.append(architecture_dict.get(arch, ""))

        build_type = self.conanfile.settings.get_safe("build_type")
        if build_type == "Release":
            compiler = self.conanfile.settings.get_safe("compiler")
            if compiler == "gcc":
                flags.append("-s")
            flags.append("-DNDEBUG")
        elif build_type == "Debug":
            flags.append("-g")

        return " ".join(flags)

    def _libcxx_flags(self):
        libcxx = self.conanfile.settings.get_safe("compiler.libcxx")
        compiler = self.conanfile.settings.get_safe("compiler")

        lib_flags = []
        if libcxx:
            lib_flags.extend(["-D%s" % define for define in stdlib_defines(compiler, libcxx)])
            lib_flags.extend(stdlib_flags(compiler, libcxx))

        return lib_flags

