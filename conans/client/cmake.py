from contextlib import contextmanager

from conans.errors import ConanException
from conans.model.settings import Settings
from conans.util.files import mkdir
from conans.tools import cpu_count
from conans import tools
import os
import platform
import subprocess
import sys


class CMake(object):

    def __init__(self, settings, generator=None, cmake_system_name=True, parallel=True):
        assert isinstance(settings, Settings)
        self._settings = settings
        self.generator = generator or self._generator()
        self.build_dir = None
        self._cmake_system_name = cmake_system_name
        self.parallel = parallel

    @staticmethod
    def options_cmd_line(options, option_upper=True, value_upper=True):
        """ FIXME: this function seems weird, not tested, not used.
        Probably should be deprecated
        """
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
            return "MinGW Makefiles"  # it is valid only under Windows

        return "Unix Makefiles"

    def _cmake_compiler_options(self, os, os_ver, arch):
        cmake_flags = []

        if str(os).lower() == "macos":
            if arch == "x86":
                cmake_flags.append("-DCMAKE_OSX_ARCHITECTURES=i386")
            # CMake defines MacOS as Darwin
            os = "Darwin"

        if self._cmake_system_name and (platform.system() != os or os_ver):
            if os:
                cmake_flags.append("-DCMAKE_SYSTEM_NAME=%s" % os)
                if os_ver:
                    cmake_flags.append("-DCMAKE_SYSTEM_VERSION=%s" % os_ver)
            else:
                cmake_flags.append("-DCMAKE_SYSTEM_NAME=Generic")

        return cmake_flags

    @property
    def is_multi_configuration(self):
        """ some IDEs are multi-configuration, as Visual. Makefiles or Ninja are single-conf
        """
        if "Visual" in self.generator or "Xcode" in self.generator:
            return True
        # TODO: complete logic
        return False

    @property
    def command_line(self):
        return _join_arguments([
            '-G "%s"' % self.generator,
            self.build_type,
            self.runtime,
            self.flags,
            '-Wno-dev'
        ])

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
        op_system_version = self._settings.get_safe("os.version")

        flags = self._cmake_compiler_options(os=op_system, os_ver=op_system_version, arch=arch)
        flags.append("-DCONAN_EXPORTED=1")
        if comp:
            flags.append('-DCONAN_COMPILER="%s"' % comp)
        if comp_version:
            flags.append('-DCONAN_COMPILER_VERSION="%s"' % comp_version)

        # Force compiler flags -- TODO: give as environment/setting parameter?
        if op_system == "Linux" or op_system == "FreeBSD" or op_system == "SunOS":
            if arch == "x86" or arch == "sparc":
                flags.extend(["-DCONAN_CXX_FLAGS=-m32",
                              "-DCONAN_SHARED_LINKER_FLAGS=-m32",
                              "-DCONAN_C_FLAGS=-m32"])
            if arch == "x86_64" or arch == "sparcv9":
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

    def configure(self, conan_file, args=None, defs=None, source_dir=None, build_dir=None):
        args = args or []
        defs = defs or {}
        source_dir = source_dir or conan_file.conanfile_directory
        self.build_dir = build_dir or self.build_dir or conan_file.conanfile_directory

        mkdir(self.build_dir)
        arg_list = _join_arguments([
            self.command_line,
            _args_to_string(args),
            _vars_to_string(defs),
            _args_to_string([source_dir])
        ])
        command = "cd %s && cmake %s" % (_args_to_string([self.build_dir]), arg_list)
        if platform.system() == "Windows" and self.generator == "MinGW Makefiles":
            with clean_sh_from_path():
                conan_file.run(command)
        else:
            conan_file.run(command)

    def build(self, conan_file, args=None, build_dir=None, target=None):
        args = args or []
        build_dir = build_dir or self.build_dir or conan_file.conanfile_directory
        if target is not None:
            args = ["--target", target] + args

        if self.parallel:
            if "Makefiles" in self.generator:
                if "--" not in args:
                    args.append("--")
                args.append("-j%i" % cpu_count())

        arg_list = _join_arguments([
            _args_to_string([build_dir]),
            self.build_config,
            _args_to_string(args)
        ])
        command = "cmake --build %s" % arg_list
        conan_file.run(command)


def _vars_to_string(defs):
    return _args_to_string('-D{0}={1}'.format(k, v) for k, v in defs.items())


def _args_to_string(args):
    if sys.platform == 'win32':
        return subprocess.list2cmdline(args)
    else:
        return " ".join("'" + arg.replace("'", r"'\''") + "'" for arg in args)


def _join_arguments(args):
    return " ".join(filter(None, args))


@contextmanager
def clean_sh_from_path():
    new_path = []
    for path_entry in os.environ.get("PATH", "").split(os.pathsep):
        if not os.path.exists(os.path.join(path_entry, "sh.exe")):
            new_path.append(path_entry)
    with tools.environment_append({"PATH": os.pathsep.join(new_path)}):
        yield
