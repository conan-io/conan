import copy
import os

from conans.client.build.compiler_flags import build_type_define, build_type_flags, format_defines, \
    include_path_option, parallel_compiler_cl_flag, visual_runtime
from conans.client.build.cppstd_flags import cppstd_flag


class VisualStudioBuildEnvironment(object):
    """
    - LIB: library paths with semicolon separator
    - CL: /I (include paths)
    - _LINK_: linker options and libraries

    https://msdn.microsoft.com/en-us/library/19z1t1wy.aspx
    https://msdn.microsoft.com/en-us/library/fwkeyyhe.aspx
    https://msdn.microsoft.com/en-us/library/9s7c9wdw.aspx
    https://msdn.microsoft.com/en-us/library/6y6t9esh.aspx

    """
    def __init__(self, conanfile, with_build_type_flags=True):
        """
        :param conanfile: ConanFile instance
        :param quote_paths: The path directories will be quoted. If you are using the vars together with
                            environment_append keep it to True, for virtualbuildenv quote_paths=False is required.
        """
        self._with_build_type_flags = with_build_type_flags

        self._conanfile = conanfile
        self._settings = conanfile.settings
        self._deps_cpp_info = conanfile.deps_cpp_info
        self._runtime = self._settings.get_safe("compiler.runtime")

        self.include_paths = conanfile.deps_cpp_info.include_paths
        self.lib_paths = conanfile.deps_cpp_info.lib_paths
        self.defines = copy.copy(conanfile.deps_cpp_info.defines)
        self.flags = self._configure_flags()
        self.cxx_flags = copy.copy(self._deps_cpp_info.cxxflags)
        self.link_flags = self._configure_link_flags()
        self.libs = conanfile.deps_cpp_info.libs
        self.std = self._std_cpp()
        self.parallel = False

    def _configure_link_flags(self):
        ret = copy.copy(self._deps_cpp_info.exelinkflags)
        ret.extend(self._deps_cpp_info.sharedlinkflags)
        return ret

    def _configure_flags(self):
        ret = copy.copy(self._deps_cpp_info.cflags)
        ret.extend(vs_build_type_flags(self._settings, with_flags=self._with_build_type_flags))
        return ret

    def _get_cl_list(self, quotes=True):
        # FIXME: It should be managed with the compiler_flags module
        # But need further investigation about the quotes and so on, so better to not break anything
        if quotes:
            ret = ['%s"%s"' % (include_path_option, lib) for lib in self.include_paths]
        else:
            ret = ['%s%s' % (include_path_option, lib) for lib in self.include_paths]

        runtime = visual_runtime(self._runtime)
        if runtime:
            ret.append(runtime)

        ret.extend(format_defines(self.defines))
        ret.extend(self.flags)
        ret.extend(self.cxx_flags)

        if self.parallel:  # Build source in parallel
            ret.append(parallel_compiler_cl_flag(output=self._conanfile.output))

        if self.std:
            ret.append(self.std)

        return ret

    def _get_link_list(self):
        def format_lib(lib):
            return lib if lib.endswith('.lib') else '%s.lib' % lib

        ret = [flag for flag in self.link_flags]  # copy
        ret.extend([format_lib(lib) for lib in self.libs])

        return ret

    @property
    def vars(self):
        """Used in conanfile with environment_append"""
        flags = self._get_cl_list()
        link_flags = self._get_link_list()

        cl_args = " ".join(flags) + _environ_value_prefix("CL")
        link_args = " ".join(link_flags)
        lib_paths = ";".join(['%s' % lib for lib in self.lib_paths]) + _environ_value_prefix("LIB", ";")
        return {"CL": cl_args,
                "LIB": lib_paths,
                "_LINK_": link_args}

    @property
    def vars_dict(self):
        """Used in virtualbuildenvironment"""
        # Here we do not quote the include paths, it's going to be used by virtual environment
        cl = self._get_cl_list(quotes=False)
        link = self._get_link_list()

        lib = [lib for lib in self.lib_paths]  # copy

        if os.environ.get("CL", None):
            cl.append(os.environ.get("CL"))

        if os.environ.get("LIB", None):
            lib.append(os.environ.get("LIB"))

        if os.environ.get("_LINK_", None):
            link.append(os.environ.get("_LINK_"))

        ret = {"CL": cl,
               "LIB": lib,
               "_LINK_": link}
        return ret

    def _std_cpp(self):
        return vs_std_cpp(self._settings)


def vs_build_type_flags(settings, with_flags=True):
    build_type = settings.get_safe("build_type")
    ret = []
    btd = build_type_define(build_type=build_type)
    if btd:
        ret.extend(format_defines([btd]))
    if with_flags:
        # When using to build a vs project we don't want to adjust these flags
        btfs = build_type_flags("Visual Studio", build_type=build_type,
                                vs_toolset=settings.get_safe("compiler.toolset"))
        if btfs:
            ret.extend(btfs)

    return ret


def vs_std_cpp(settings):
    if settings.get_safe("compiler") == "Visual Studio" and \
       settings.get_safe("cppstd"):
        flag = cppstd_flag(settings.get_safe("compiler"),
                           settings.get_safe("compiler.version"),
                           settings.get_safe("cppstd"))
        return flag
    return None


def _environ_value_prefix(var_name, prefix=" "):
    if os.environ.get(var_name, ""):
        return "%s%s" % (prefix, os.environ.get(var_name, ""))
    else:
        return ""
