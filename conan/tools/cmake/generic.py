import os
import re
import textwrap

from jinja2 import Template

from conan.tools._compilers import architecture_flag
from conans.client.tools import cpu_count
from conans.util.files import load
from conans.errors import ConanException
from conan.tools.cmake.base import CMakeToolchainBase
from conan.tools.cmake.utils import get_generator, is_multi_configuration


# https://stackoverflow.com/questions/30503631/cmake-in-which-order-are-files-parsed-cache-toolchain-etc
# https://cmake.org/cmake/help/v3.6/manual/cmake-toolchains.7.html
# https://github.com/microsoft/vcpkg/tree/master/scripts/buildsystems


def get_toolset(settings, generator):
    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    if compiler == "Visual Studio":
        subs_toolset = settings.get_safe("compiler.toolset")
        if subs_toolset:
            return subs_toolset
    elif compiler == "intel" and compiler_base == "Visual Studio" and "Visual" in generator:
        compiler_version = settings.get_safe("compiler.version")
        if compiler_version:
            compiler_version = compiler_version if "." in compiler_version else \
                "%s.0" % compiler_version
            return "Intel C++ Compiler " + compiler_version
    return None


def get_generator_platform(settings, generator):
    # Returns the generator platform to be used by CMake
    if "CONAN_CMAKE_GENERATOR_PLATFORM" in os.environ:
        return os.environ["CONAN_CMAKE_GENERATOR_PLATFORM"]

    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    arch = settings.get_safe("arch")

    if settings.get_safe("os") == "WindowsCE":
        return settings.get_safe("os.platform")

    if (compiler in ("Visual Studio", "msvc") or compiler_base == "Visual Studio") and \
            generator and "Visual" in generator:
        return {"x86": "Win32",
                "x86_64": "x64",
                "armv7": "ARM",
                "armv8": "ARM64"}.get(arch)
    return None


class CMakeGenericToolchain(CMakeToolchainBase):

    def __init__(self, conanfile):

        self.generator = generator or get_generator(self._conanfile)
        self.generator_platform = (generator_platform or
                                   get_generator_platform(self._conanfile.settings,
                                                          self.generator))
        self.toolset = toolset or get_toolset(self._conanfile.settings, self.generator)
        if (self.generator is not None and "Ninja" in self.generator
                and "Visual" in self._conanfile.settings.compiler):
            self.compiler = "cl"
        else:
            self.compiler = None  # compiler defined by default


