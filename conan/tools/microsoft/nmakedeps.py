import os

from conan.internal import check_duplicated_generator
from conan.tools.env import Environment
from conans.model.build_info import CppInfo


class NMakeDeps(object):

    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        self._conanfile = conanfile
        self._environment = None

    # TODO: This is similar from AutotoolsDeps: Refactor and make common
    def _get_cpp_info(self):
        ret = CppInfo()
        deps = self._conanfile.dependencies.host.topological_sort
        deps = [dep for dep in reversed(deps.values())]
        for dep in deps:
            dep_cppinfo = dep.cpp_info.aggregated_components()
            # In case we have components, aggregate them, we do not support isolated
            # "targets" with autotools
            ret.merge(dep_cppinfo)
        return ret

    @property
    def environment(self):
        # TODO: Seems we want to make this uniform, equal to other generators
        if self._environment is None:
            cpp_info = self._get_cpp_info()

            lib_paths = ";".join(cpp_info.libdirs or [])

            def format_lib(lib):
                ext = os.path.splitext(lib)[1]
                return lib if ext in (".so", ".lib", ".a", ".dylib", ".bc") else '%s.lib' % lib

            ret = []
            ret.extend(cpp_info.exelinkflags or [])
            ret.extend(cpp_info.sharedlinkflags or [])
            ret.extend([format_lib(lib) for lib in cpp_info.libs or []])
            link_args = " ".join(ret)

            cl_flags = [f'-I"{p}"' for p in cpp_info.includedirs or []]
            cl_flags.extend(cpp_info.cflags or [])
            cl_flags.extend(cpp_info.cxxflags or [])

            env = Environment()
            env.append("CL", " ".join(cl_flags))
            env.append_path("LIB", lib_paths)
            env.append("_LINK_", link_args)
            self._environment = env
        return self._environment

    def vars(self, scope="build"):
        return self.environment.vars(self._conanfile, scope=scope)

    def generate(self, scope="build"):
        check_duplicated_generator(self, self._conanfile)
        self.vars(scope).save_script("conannmakedeps")
