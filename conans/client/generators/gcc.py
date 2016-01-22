from conans.model import Generator
from conans.paths import BUILD_INFO_GCC


class GCCGenerator(Generator):
    @property
    def filename(self):
        return BUILD_INFO_GCC

    @property
    def content(self):
        """With gcc_flags you can invoke gcc like that:
        $ gcc main.c @conanbuildinfo.gcc -o main
        """
        defines = " ".join("-D%s" % x for x in self._deps_build_info.defines)
        include_paths = " ".join("-I%s"
                                 % x.replace("\\", "/") for x in self._deps_build_info.include_paths)
        rpaths = " ".join("-Wl,-rpath=%s"
                          % x.replace("\\", "/") for x in self._deps_build_info.lib_paths)
        lib_paths = " ".join("-L%s" % x.replace("\\", "/") for x in self._deps_build_info.lib_paths)
        libs = " ".join("-l%s" % x for x in self._deps_build_info.libs)
        other_flags = " ".join(self._deps_build_info.cppflags +
                               self._deps_build_info.cflags +
                               self._deps_build_info.sharedlinkflags +
                               self._deps_build_info.exelinkflags)
        flags = ("%s %s %s %s %s %s"
                 % (defines, include_paths, lib_paths, rpaths, libs, other_flags))
        return flags
