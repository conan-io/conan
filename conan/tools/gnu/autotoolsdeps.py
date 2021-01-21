import platform

from conans.client.envvars.environment import env_files
from conans.util.files import save


def format_include_paths(include_paths, settings, win_bash=False, subsystem=None):
    return ["%s%s" % (include_path_option, adjust_path(include_path, settings, win_bash=win_bash,
                                                       subsystem=subsystem))
            for include_path in include_paths if include_path]


def format_library_paths(library_paths, settings, win_bash=False, subsystem=None):
    compiler = _base_compiler(settings)
    pattern = "-LIBPATH:%s" if str(compiler) == 'Visual Studio' else "-L%s"
    return [pattern % adjust_path(library_path, settings, win_bash=win_bash,
                                  subsystem=subsystem)
            for library_path in library_paths if library_path]


class AutotoolsDeps(object):
    def __init__(self, conanfile):
        # Set the generic objects before mapping to env vars to let the user
        # alter some value
        self.libs = list(self._deps_cpp_info.libs)
        self.libs.extend(list(self._deps_cpp_info.system_libs))
        self.include_paths = list(self._deps_cpp_info.include_paths)
        self.library_paths = list(self._deps_cpp_info.lib_paths)
        self.defines = list(self._deps_cpp_info.defines)
        self.flags = list(self._deps_cpp_info.cflags)
        self.cxx_flags = list(self._deps_cpp_info.cxxflags)

        srf = sysroot_flag(self._deps_cpp_info.sysroot,
                           self._conanfile.settings,
                           win_bash=self._win_bash,
                           subsystem=self.subsystem)
        if srf:
            self.flags.append(srf)

        # Not -L flags, ["-m64" "-m32"]
        self.link_flags = self._configure_link_flags()  # TEST!

    def generate(self):
        result = {}
        # FIXME: REplace with settings_build.os
        v = self._vars
        append_with_spaces = ["CPPFLAGS", "CFLAGS", "CXXFLAGS", "LIBS", "LDFLAGS", "CL", "_LINK_"]
        suffix = ""
        venv_name = "conanenv"
        if platform.system() == "Windows":
            result.update(env_files(v, self.append_with_spaces, BAT_FLAVOR, self.output_path,
                                    self.suffix, self.venv_name))
        else:
            result.update(env_files(v, self.append_with_spaces, SH_FLAVOR, self.output_path,
                                    self.suffix, self.venv_name))
        for f, c in result.items():
            save(f, c)

    def _configure_link_flags(self):
        """Not the -L"""
        ret = list(self._deps_cpp_info.sharedlinkflags)
        ret.extend(list(self._deps_cpp_info.exelinkflags))
        ret.extend(format_frameworks(self._deps_cpp_info.frameworks, self._conanfile.settings))
        ret.extend(format_framework_paths(self._deps_cpp_info.framework_paths,
                                          self._conanfile.settings))

        sysf = sysroot_flag(self._deps_cpp_info.sysroot,
                            self._conanfile.settings,
                            win_bash=self._win_bash,
                            subsystem=self.subsystem)
        if sysf:
            ret.append(sysf)

        return ret

    def _get_vars(self):
        def append(*args):
            ret = []
            for arg in args:
                if arg:
                    if isinstance(arg, list):
                        ret.extend(arg)
                    else:
                        ret.append(arg)
            return ret
        lib_paths = format_library_paths(self.library_paths,
                                         self._conanfile.settings,
                                         win_bash=self._win_bash,
                                         subsystem=self.subsystem)
        include_paths = format_include_paths(self.include_paths,
                                             self._conanfile.settings,
                                             win_bash=self._win_bash,
                                             subsystem=self.subsystem)

        ld_flags = append(self.link_flags, lib_paths)
        cpp_flags = append(include_paths, format_defines(self.defines))
        libs = format_libraries(self.libs, self._conanfile.settings)

    @property
    def _vars(self):
        ld_flags, cpp_flags, libs, cxx_flags, c_flags = self._get_vars()

        cpp_flags = " ".join(cpp_flags) + _environ_value_prefix("CPPFLAGS")
        cxx_flags = " ".join(cxx_flags) + _environ_value_prefix("CXXFLAGS")
        cflags = " ".join(c_flags) + _environ_value_prefix("CFLAGS")
        ldflags = " ".join(ld_flags) + _environ_value_prefix("LDFLAGS")
        libs = " ".join(libs) + _environ_value_prefix("LIBS")

        ret = {"CPPFLAGS": cpp_flags.strip(),
               "CXXFLAGS": cxx_flags.strip(),
               "CFLAGS": cflags.strip(),
               "LDFLAGS": ldflags.strip(),
               "LIBS": libs.strip()
               }

        return ret


def _environ_value_prefix(var_name, prefix=" "):
    if os.environ.get(var_name, ""):
        return "%s%s" % (prefix, os.environ.get(var_name, ""))
    else:
        return ""
