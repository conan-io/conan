import copy
import os


class VisualStudioBuildEnvironment(object):
    """
    - LIB: library paths with semicolon separator
    - CL: /I (include paths)

    https://msdn.microsoft.com/en-us/library/19z1t1wy.aspx
    https://msdn.microsoft.com/en-us/library/fwkeyyhe.aspx
    https://msdn.microsoft.com/en-us/library/9s7c9wdw.aspx

    """
    def __init__(self, conanfile):
        """
        :param conanfile: ConanFile instance
        :param quote_paths: The path directories will be quoted. If you are using the vars together with
                            environment_append keep it to True, for virtualbuildenv quote_paths=False is required.
        """
        self._settings = conanfile.settings
        self._options = conanfile.options
        self._deps_cpp_info = conanfile.deps_cpp_info

        self.include_paths = conanfile.deps_cpp_info.include_paths
        self.lib_paths = conanfile.deps_cpp_info.lib_paths
        self.defines = copy.copy(conanfile.deps_cpp_info.defines)
        self.runtime = conanfile.settings.get_safe("compiler.runtime")
        self.flags = self._configure_flags()
        self.cxx_flags = copy.copy(self._deps_cpp_info.cppflags)
        self.link_flags = self._configure_link_flags()

    def _configure_link_flags(self):
        ret = copy.copy(self._deps_cpp_info.exelinkflags)
        ret.extend(self._deps_cpp_info.sharedlinkflags)
        return ret

    def _configure_flags(self):
        ret = copy.copy(self._deps_cpp_info.cflags)
        if self._settings.get_safe("build_type") == "Debug":
            ret.append("/Zi")  # default debug information
        return ret

    def _get_cl_list(self, quotes=True):
        if quotes:
            ret = ['/I"%s"' % lib for lib in self.include_paths]
        else:
            ret = ['/I%s' % lib for lib in self.include_paths]

        if self.runtime:
            ret.append("/%s" % self.runtime)

        ret.extend(['/D%s' % lib for lib in self.defines])
        ret.extend(self.flags)
        ret.extend(self.cxx_flags)
        ret.extend(self.link_flags)

        return ret

    @property
    def vars(self):
        """Used in conanfile with environment_append"""
        flags = self._get_cl_list()
        cl_args = " ".join(flags) + _environ_value_prefix("CL")
        lib_paths = ";".join(['%s' % lib for lib in self.lib_paths]) + _environ_value_prefix("LIB", ";")
        return {"CL": cl_args,
                "LIB": lib_paths}

    @property
    def vars_dict(self):
        """Used in virtualbuildenvironment"""
        # Here we do not quote the include paths, it's going to be used by virtual environment
        cl = self._get_cl_list(quotes=False)

        lib = [lib for lib in self.lib_paths]  # copy

        if os.environ.get("CL", None):
            cl.append(os.environ.get("CL"))

        if os.environ.get("LIB", None):
            lib.append(os.environ.get("LIB"))

        ret = {"CL": cl,
               "LIB": lib}
        return ret


def _environ_value_prefix(var_name, prefix=" "):
    if os.environ.get(var_name, ""):
        return "%s%s" % (prefix, os.environ.get(var_name, ""))
    else:
        return ""
