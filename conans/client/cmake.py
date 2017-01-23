from conans.errors import ConanException
from conans.model.settings import Settings
import os
import platform

class CMake(object):

    def __init__(self, settings):
        assert isinstance(settings, Settings)
        self._settings = settings
        self.generator = self._generator()

    @staticmethod
    def options_cmd_line(options, option_upper=True, value_upper=True):
        result = []
        for option, value in options.values.as_list():
            if value is not None:
                option = option.upper() if option_upper else option
                value = value.upper() if value_upper else value
                result.append("-D%s=%s" % (option, value))
        return ' '.join(result)

    def _generator(self):
        if (not self._settings.compiler or
                not self._settings.compiler.version or
                not self._settings.arch):
            raise ConanException("You must specify compiler, compiler.version and arch in "
                                 "your settings to use a CMake generator")

        operating_system = str(self._settings.os) if self._settings.os else None
        compiler = str(self._settings.compiler) if self._settings.compiler else None
        arch = str(self._settings.arch) if self._settings.arch else None
        host_platform = platform.system()

        if "CONAN_CMAKE_GENERATOR" in os.environ:
            return os.environ["CONAN_CMAKE_GENERATOR"]

        if compiler == "Visual Studio":
            _visuals = {'8': '8 2005',
                        '9': '9 2008',
                        '10': '10 2010',
                        '11': '11 2012',
                        '12': '12 2013',
                        '14': '14 2015',
                        '15': '15 2017'}
            str_ver = str(self._settings.compiler.version)
            base = "Visual Studio %s" % _visuals.get(str_ver, "UnknownVersion %s" % str_ver)
            if arch == "x86_64":
                return base + " Win64"
            elif "arm" in str(arch):
                return base + " ARM"
            else:
                return base

        if operating_system == "Windows":
            non_msvc = (compiler != "Visual Studio")
            if host_platform == operating_system and non_msvc:
                return "MinGW Makefiles" #it is valid only under Windows
            elif non_msvc:
                return "Unix Makefiles"
        if operating_system == "Linux":
            if compiler in ["gcc", "clang", "apple-clang"]:
                return "Unix Makefiles"
        if operating_system == "Macos":
            if compiler in ["gcc", "clang", "apple-clang"]:
                return "Unix Makefiles"
        if operating_system == "FreeBSD":
            if compiler in ["gcc", "clang", "apple-clang"]:
                return "Unix Makefiles"
        if operating_system == "SunOS":
            if compiler in ["sun-cc", "gcc"]:
                return "Unix Makefiles"

        raise ConanException("Unknown cmake generator for these settings")

    def _cmake_compiler_options(self, target_os, target_arch, target_comp):
        host_platform = platform.system()
        same_platform = (target_os == host_platform)

        cmake_flags = []
        cmake_flags.append("-DCMAKE_SYSTEM_NAME=%s" % target_os)

        if target_comp == "clang":
            cmake_flags.append("-DCMAKE_C_COMPILER=clang")
            cmake_flags.append("-DCMAKE_CXX_COMPILER=clang++")
        elif target_comp == "gcc":
            if target_os == "Windows" and not same_platform:
                if target_arch == "x86":
                    cmake_flags.append("-DCMAKE_C_COMPILER=i686-w64-mingw32-gcc")
                    cmake_flags.append("-DCMAKE_CXX_COMPILER=i686-w64-mingw32-g++")
                else:
                    cmake_flags.append("-DCMAKE_C_COMPILER=x86_64-w64-mingw32-gcc")
                    cmake_flags.append("-DCMAKE_CXX_COMPILER=x86_64-w64-mingw32-g++")
            else:
                cmake_flags.append("-DCMAKE_C_COMPILER=gcc")
                cmake_flags.append("-DCMAKE_CXX_COMPILER=g++")

        if target_arch == "x86" and target_os == "Macos":
            cmake_flags.append("-DCMAKE_OSX_ARCHITECTURES=i386")

        return cmake_flags

    @property
    def is_multi_configuration(self):
        """ some IDEs are multi-configuration, as Visual. Makefiles or Ninja are single-conf
        """
        if "Visual" in self.generator:
            return True
        # TODO: complete logic
        return False

    @property
    def command_line(self):
        return '-G "%s" %s %s %s -Wno-dev' % (self.generator, self.build_type,
                                              self.runtime, self.flags)

    @property
    def build_type(self):
        try:
            build_type = self._settings.build_type
        except ConanException:
            return ""
        if build_type and not self.is_multi_configuration:
            return "-DCMAKE_BUILD_TYPE=%s" % build_type
        return ""

    @property
    def build_config(self):
        """ cmake --build tool have a --config option for Multi-configuration IDEs
        """
        try:
            build_type = self._settings.build_type
        except ConanException:
            return ""
        if build_type and self.is_multi_configuration:
            return "--config %s" % build_type
        return ""

    @property
    def flags(self):
        op_system = str(self._settings.os) if self._settings.os else None
        arch = str(self._settings.arch) if self._settings.arch else None
        comp = str(self._settings.compiler) if self._settings.compiler else None
        comp_version = self._settings.compiler.version

        flags = []
        flags = self._cmake_compiler_options(target_os=op_system, target_arch=arch, target_comp=comp)

        if comp:
            flags.append('-DCONAN_COMPILER="%s"' % comp)
        if comp_version:
            flags.append('-DCONAN_COMPILER_VERSION="%s"' % comp_version)

        if op_system == "Linux" or op_system == "FreeBSD" or op_system == "SunOS":
            if arch == "x86":
                flags.extend(["-DCONAN_CXX_FLAGS=-m32",
                              "-DCONAN_SHARED_LINKER_FLAGS=-m32",
                              "-DCONAN_C_FLAGS=-m32"])
            if arch == "x86_64":
                flags.extend(["-DCONAN_CXX_FLAGS=-m64",
                              "-DCONAN_SHARED_LINKER_FLAGS=-m64",
                              "-DCONAN_C_FLAGS=-m64"])
        try:
            libcxx = self._settings.compiler.libcxx
            flags.append('-DCONAN_LIBCXX="%s"' % libcxx)
        except:
            pass
        return " ".join(flags)

    @property
    def runtime(self):
        try:
            runtime = self._settings.compiler.runtime
        except ConanException:
            return ""
        if runtime:
            return "-DCONAN_LINK_RUNTIME=/%s" % runtime
        return ""
