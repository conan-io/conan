from conans.client.configure_build_environment import sun_cc_libcxx_flags_dict
from conans.model import Generator
from conans.model.settings import get_setting_str_safe
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
        arch = get_setting_str_safe(self.conanfile.settings, "arch")
        flags.append({"x86_64": "-m64", "x86": "-m32"}.get(arch, ""))
        return " ".join(flags)

    def _libcxx_flags(self):
        libcxx = get_setting_str_safe(self.conanfile.settings, "compiler.libcxx")
        compiler = get_setting_str_safe(self.conanfile.settings, "compiler")

        lib_flags = []
        if libcxx:
            if libcxx == "libstdc++":
                lib_flags.append("-D_GLIBCXX_USE_CXX11_ABI=0")
            elif str(libcxx) == "libstdc++11":
                lib_flags.append("-D_GLIBCXX_USE_CXX11_ABI=1")

            if "clang" in compiler:
                lib_flags.append({"libc++": "-stdlib=libc++"}.get(libcxx, "-stdlib=libstdc++"))

            elif compiler == "sun-cc":
                lib_flags.append(sun_cc_libcxx_flags_dict.get(libcxx, ""))

        return lib_flags

