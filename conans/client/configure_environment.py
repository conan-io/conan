from conans.model.settings import Settings
import copy


class ConfigureEnvironment(object):

    def __init__(self, deps_cpp_info, settings):
        assert isinstance(settings, Settings)
        self._settings = settings
        self._deps_cpp_info = deps_cpp_info
        self.compiler = getattr(self._settings, "compiler", None)
        self.arch = getattr(self._settings, "arch", None)
        self.os = getattr(self._settings, "os", None)
        self.build_type = getattr(self._settings, "build_type", None)
        self.libcxx = None
        try:
            self.libcxx = self.compiler.libcxx
        except:
            pass

    @property
    def command_line(self):
        """
            env = ConfigureEnvironment(self.deps_cpp_info, self.settings)
            command = '%s && nmake /f Makefile.msvc"' % env.command_line
            self.run(command)
        """
        command = ""
        if self.os == "Linux" or self.os == "Macos":
            libs = 'LIBS="%s"' % " ".join(["-l%s" % lib for lib in self._deps_cpp_info.libs])
            archflag = "-m32" if self.arch == "x86" else ""
            ldflags = 'LDFLAGS="%s %s"' % (" ".join(["-L%s" % lib for lib in self._deps_cpp_info.lib_paths]), archflag)
            debug = "-g" if self.build_type == "Debug" else "-s -DNDEBUG"
            cflags = 'CFLAGS="%s %s %s"' % (archflag, " ".join(self._deps_cpp_info.cflags), debug)
            cpp_flags = 'CPPFLAGS="%s %s %s"' % (archflag, " ".join(self._deps_cpp_info.cppflags), debug)

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

            cpp_flags = 'CPPFLAGS="%s %s"' % (archflag, " ".join(all_cpp_flags))
            include_paths = ":".join(['"%s"' % lib for lib in self._deps_cpp_info.include_paths])
            headers_flags = 'C_INCLUDE_PATH=%s CPP_INCLUDE_PATH=%s' % (include_paths, include_paths)

            command = "env %s %s %s %s %s" % (libs, ldflags, cflags, cpp_flags, headers_flags)
        elif self.os == "Windows" and self.compiler == "Visual Studio":
            cl_args = " ".join(['/I"%s"' % lib for lib in self._deps_cpp_info.include_paths])
            lib_paths = ";".join(['"%s"' % lib for lib in self._deps_cpp_info.lib_paths])
            command = "SET LIB=%s;%%LIB%% && SET CL=%s" % (lib_paths, cl_args)
        return command
