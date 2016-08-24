from conans.model.settings import Settings
import copy
from conans.client.generators.virtualenv import get_setenv_variables_commands
from conans.model.env_info import DepsEnvInfo


class ConfigureEnvironment(object):

    def __init__(self, *args):
        if len(args) == 2:
            deps_cpp_info = args[0]
            deps_env_info = DepsEnvInfo()
            settings = args[1]
        elif len(args) == 1:  # conanfile (new interface)
            self.conanfile = args[0]
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
            self.libcxx = str(self.compiler.libcxx)
        except:
            self.libcxx = None

    @property
    def command_line(self):
        """
            env = ConfigureEnvironment(self.deps_cpp_info, self.settings)
            command = '%s && nmake /f Makefile.msvc"' % env.command_line
            self.run(command)
        """
        command = ""
        if self.os == "Linux" or self.os == "Macos" or (self.os == "Windows" and
                                                        self.compiler == "gcc"):
            libflags = " ".join(["-l%s" % lib for lib in self._deps_cpp_info.libs])
            libs = 'LIBS="%s"' % libflags
            archflag = "-m32" if self.arch == "x86" else ""
            exe_linker_flags = " ".join(self._deps_cpp_info.exelinkflags)
            shared_linker_flags = " ".join(self._deps_cpp_info.sharedlinkflags)
            lib_paths = " ".join(["-L%s" % lib for lib in self._deps_cpp_info.lib_paths])
            ldflags = 'LDFLAGS="%s %s %s %s %s"' % (lib_paths, libflags, archflag,
                                                    exe_linker_flags, shared_linker_flags)
            debug = "-g" if self.build_type == "Debug" else "-s -DNDEBUG"
            include_flags = " ".join(['-I%s' % i for i in self._deps_cpp_info.include_paths])
            cflags = 'CFLAGS="%s %s %s %s"' % (archflag, " ".join(self._deps_cpp_info.cflags),
                                               debug, include_flags)

            # Append the definition for libcxx
            all_cpp_flags = copy.copy(self._deps_cpp_info.cppflags)
            if self.libcxx:
                if str(self.libcxx) == "libstdc++":
                    all_cpp_flags.append("-D_GLIBCXX_USE_CXX11_ABI=0")
                elif str(self.libcxx) == "libstdc++11":
                    all_cpp_flags.append("-D_GLIBCXX_USE_CXX11_ABI=1")

                if "clang" in str(self.compiler):
                    if str(self.libcxx) == "libc++":
                        all_cpp_flags.append("-stdlib=libc++")
                    else:
                        all_cpp_flags.append("-stdlib=libstdc++")

            cpp_flags = 'CPPFLAGS="%s %s %s %s"' % (archflag, " ".join(all_cpp_flags),
                                                    debug, include_flags)
            include_paths = ":".join(['"%s"' % lib for lib in self._deps_cpp_info.include_paths])
            headers_flags = 'C_INCLUDE_PATH={0} CPP_INCLUDE_PATH={0}'.format(include_paths)
            command = "env %s %s %s %s %s" % (libs, ldflags, cflags, cpp_flags, headers_flags)
        elif self.os == "Windows" and self.compiler == "Visual Studio":
            cl_args = " ".join(['/I"%s"' % lib for lib in self._deps_cpp_info.include_paths])
            lib_paths = ";".join(['"%s"' % lib for lib in self._deps_cpp_info.lib_paths])
            command = "SET LIB=%s;%%LIB%% && SET CL=%s" % (lib_paths, cl_args)

        # Add the rest of env variables from deps_env_info
        command += " ".join(get_setenv_variables_commands(self._deps_env_info,
                                                          "" if self.os != "Windows" else "SET"))
        return command
