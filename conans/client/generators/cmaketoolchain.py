import shlex
import os

from conans.paths import BUILD_INFO_CMAKETOOLCHAIN
from conans.model import Generator

class CMakeToolchainGenerator(Generator):
    @property
    def filename(self):
        return BUILD_INFO_CMAKETOOLCHAIN

    def cmake_system_name(self):
        names = {
            "Macos": "Darwin",
            "iOS": "Darwin",
        }

        osname = str(self.conanfile.settings.os)

        if osname in names:
            return names[osname]

        return osname

    @property
    def content(self):

        def make_absolute(prg):
            if os.path.isabs(prg):
                return prg

            for path in os.environ.get("PATH", "").split(os.pathsep):
                binpath = os.path.join(path, prg)
                if os.path.exists(binpath):
                    return str(binpath)

            return prg

        def split_ccache(env, default=""):
            envstr = self.conanfile.env.get(env, default)
            if "ccache" in envstr:
                lexsplit = shlex.split(envstr)
                lexsplit = [make_absolute(a) for a in lexsplit]
                argstr = ""

                if len(lexsplit) > 1:
                    argstr = " ".join(lexsplit[1:])

                return (make_absolute(lexsplit[0]), argstr)

            return (envstr, "")


        cc, ccarg1 = split_ccache("CC", "cc")
        cxx, cxxarg1 = split_ccache("CXX", "c++")

        cmakevars = {
            "CMAKE_SYSTEM_PROCESSOR": str(self.conanfile.settings.arch),
            "CMAKE_SYSTEM_NAME": self.cmake_system_name(),
            "CMAKE_C_COMPILER": cc,
            "CMAKE_C_COMPILER_ARG1": ccarg1,
            "CMAKE_CXX_COMPILER": cxx,
            "CMAKE_CXX_COMPILER_ARG1": cxxarg1,
            "CMAKE_SYSTEM_VERSION": "1",
        }

        ldflags = self.conanfile.env.get("LDFLAGS", "")

        cmakeforcedvars = {
            "CMAKE_C_FLAGS": self.conanfile.env.get("CFLAGS", ""),
            "CMAKE_CXX_FLAGS": self.conanfile.env.get("CXXFLAGS", ""),
            "CMAKE_SHARED_LINKER_FLAGS": ldflags,
            "CMAKE_EXE_LINKER_FLAGS": ldflags,
            "CMAKE_MODULE_LINKER_FLAGS": ldflags,
            "CMAKE_STATIC_LINKER_FLAGS": ldflags
        }

        if self.conanfile.settings.os == "iOS":
            cmakevars["IOS"] = "TRUE"

        cmakedata = "\n".join("set(%s \"%s\")" % (key, value) for key, value in cmakevars.items())
        cmakedata += "\n"

        cmakedata += "\n".join("set(%s \"%s\" CACHE STRING \"\" FORCE)" % (key, value)
                               for key, value in cmakeforcedvars.items())
        cmakedata += "\n"

        return cmakedata
