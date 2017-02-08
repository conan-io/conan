from conans.model.settings import Settings
import copy
from conans.client.generators.virtualenv import get_setenv_variables_commands
from conans.model.env_info import DepsEnvInfo
from conans.util.files import save
from conans import tools
from conans.client.output import ConanOutput
import sys


class ConfigureEnvironment(object):

    def __init__(self, *args):
        if len(args) == 2:
            deps_cpp_info = args[0]
            deps_env_info = DepsEnvInfo()
            settings = args[1]
            self.output = ConanOutput(sys.stdout)
        elif len(args) == 1:  # conanfile (new interface)
            self.conanfile = args[0]
            self.output = self.conanfile.output
            deps_cpp_info = self.conanfile.deps_cpp_info
            deps_env_info = self.conanfile.deps_env_info
            settings = self.conanfile.settings

        assert isinstance(settings, Settings)

        self._settings = settings
        self._deps_cpp_info = deps_cpp_info
        self._deps_env_info = deps_env_info
        try:
            self.compiler = str(self._settings.compiler)
        except:
            self.compiler = None

        try:
            self.arch = str(self._settings.arch)
        except:
            self.arch = None

        try:
            self.os = str(self._settings.os)
        except:
            self.os = None

        try:
            self.build_type = str(self._settings.build_type)
        except:
            self.build_type = None

        try:
            self.libcxx = str(self._settings.compiler.libcxx)
        except:
            self.libcxx = None

    def _gcc_arch_flags(self):
        if self.arch == "x86_64":
            return "-m64"
        elif self.arch == "x86":
            return "-m32"
        else:
            return "";

    def _gcc_lib_flags(self):
        lib_flags = []
        if self.libcxx:
            if str(self.libcxx) == "libstdc++":
                lib_flags.append("-D_GLIBCXX_USE_CXX11_ABI=0")
            elif str(self.libcxx) == "libstdc++11":
                lib_flags.append("-D_GLIBCXX_USE_CXX11_ABI=1")

            if "clang" in str(self.compiler):
                if str(self.libcxx) == "libc++":
                    lib_flags.append("-stdlib=libc++")
                else:
                    lib_flags.append("-stdlib=libstdc++")

            elif str(self.compiler) == "sun-cc":
                if str(self.libcxx) == "libCstd":
                    lib_flags.append("-library=Cstd")
                elif str(self.libcxx) == "libstdcxx":
                    lib_flags.append("-library=stdcxx4")
                elif str(self.libcxx) == "libstlport":
                    lib_flags.append("-library=stlport4")
                elif str(self.libcxx) == "libstdc++":
                    lib_flags.append("-library=stdcpp")

        return lib_flags

    def _gcc_env(self):
        libflags = " ".join(["-l%s" % lib for lib in self._deps_cpp_info.libs])
        libs = 'LIBS="%s"' % libflags
        archflag = self._gcc_arch_flags()
        exe_linker_flags = " ".join(self._deps_cpp_info.exelinkflags)
        shared_linker_flags = " ".join(self._deps_cpp_info.sharedlinkflags)
        lib_paths = " ".join(["-L%s" % lib for lib in self._deps_cpp_info.lib_paths])
        ldflags = 'LDFLAGS="%s %s %s %s $LDFLAGS"' % (lib_paths, archflag,
                                                      exe_linker_flags, shared_linker_flags)
        if self.build_type == "Debug":
            debug = "-g"
        else:
            debug = "-s -DNDEBUG" if self.compiler == "gcc" else "-DNDEBUG"
        include_flags = " ".join(['-I%s' % i for i in self._deps_cpp_info.include_paths])
        defines = " ".join(['-D%s' % i for i in self._deps_cpp_info.defines])
        cflags = 'CFLAGS="$CFLAGS %s %s %s %s %s"' % (archflag,
                                                      " ".join(self._deps_cpp_info.cflags),
                                                      debug, include_flags, defines)

        # Append the definition for libcxx
        all_cpp_flags = copy.copy(self._deps_cpp_info.cppflags)
        all_cpp_flags.extend(self._gcc_lib_flags())

        cpp_flags = 'CPPFLAGS="$CPPFLAGS %s %s %s %s %s"' % (archflag, " ".join(all_cpp_flags),
                                                             debug, include_flags, defines)
        include_paths = ":".join(['"%s"' % lib for lib in self._deps_cpp_info.include_paths])
        headers_flags = ('C_INCLUDE_PATH=$C_INCLUDE_PATH:{0} '
                         'CPLUS_INCLUDE_PATH=$CPLUS_INCLUDE_PATH:{0}'.format(include_paths))
        command = "env %s %s %s %s %s" % (libs, ldflags, cflags, cpp_flags, headers_flags)
        # Do not include "export" command, they are passed to env
        command += " ".join(get_setenv_variables_commands(self._deps_env_info, ""))
        return command

    @property
    def command_line_env(self):
        if self.os == "Linux" or self.os == "Macos" or self.os == "FreeBSD" or self.os == "SunOS":
            if self.compiler == "gcc" or "clang" in str(self.compiler) or "sun-cc" in str(self.compiler):
                return self._gcc_env()
        elif self.os == "Windows":
            commands = []
            commands.append("@echo off")
            vcvars = ""
            if self.compiler == "Visual Studio":
                cl_args = " ".join(['/I"%s"' % lib for lib in self._deps_cpp_info.include_paths])
                lib_paths = ";".join(['%s' % lib for lib in self._deps_cpp_info.lib_paths])
                commands.append('if defined LIB (SET "LIB=%LIB%;{0}") else (SET "LIB={0}")'.
                                format(lib_paths))
                commands.append('if defined CL (SET "CL=%CL% {0}") else (SET "CL={0}")'.
                                format(cl_args))
                vcvars = tools.vcvars_command(self._settings)
                if vcvars:
                    vcvars += " && "
            elif self.compiler == "gcc":
                include_paths = ";".join(['%s'
                                          % lib for lib in self._deps_cpp_info.include_paths])
                commands.append('if defined C_INCLUDE_PATH (SET "C_INCLUDE_PATH=%C_INCLUDE_PATH%;{0}")'
                                ' else (SET "C_INCLUDE_PATH={0}")'.format(include_paths))
                commands.append('if defined CPLUS_INCLUDE_PATH '
                                '(SET "CPLUS_INCLUDE_PATH=%CPLUS_INCLUDE_PATH%;{0}")'
                                ' else (SET "CPLUS_INCLUDE_PATH={0}")'.format(include_paths))

                lib_paths = ";".join([lib for lib in self._deps_cpp_info.lib_paths])
                commands.append('if defined LIBRARY_PATH (SET "LIBRARY_PATH=%LIBRARY_PATH%;{0}")'
                                ' else (SET "LIBRARY_PATH={0}")'.format(lib_paths))

            commands.extend(get_setenv_variables_commands(self._deps_env_info, "SET"))
            save("_conan_env.bat", "\r\n".join(commands))
            command = "%scall _conan_env.bat" % vcvars
            return command

        return " && ".join(get_setenv_variables_commands(self._deps_env_info))

    # alias for backward compatibility
    command_line = command_line_env

    @property
    def compile_flags(self):
        if self.compiler == "gcc" or "clang" in str(self.compiler) or self.compiler == "sun-cc":
            flags = []
            flags.extend("-l%s" % lib for lib in self._deps_cpp_info.libs)
            flags.append(self._gcc_arch_flags())
            flags.extend(self._deps_cpp_info.exelinkflags)
            flags.extend(self._deps_cpp_info.sharedlinkflags)
            if self.build_type == "Debug":
                flags.append("-g")
            else:
                flags.append("-s -DNDEBUG" if self.compiler == "gcc" else "-DNDEBUG")
            flags.extend('-D%s' % i for i in self._deps_cpp_info.defines)
            flags.extend('-I"%s"' % i for i in self._deps_cpp_info.include_paths)
            flags.extend('-L"%s"' % i for i in self._deps_cpp_info.lib_paths)
            flags.extend(self._deps_cpp_info.cppflags)
            flags.extend(self._gcc_lib_flags())

            return " ".join(flags)
        if self.compiler == "Visual Studio":
            libs = " ".join("%s.lib" % lib for lib in self._deps_cpp_info.libs)
            return libs

        return ""
