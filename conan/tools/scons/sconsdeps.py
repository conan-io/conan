from jinja2 import Template

from conan.tools._check_build_profile import check_using_build_profile
from conans.model.new_build_info import NewCppInfo
from conans.util.files import save


class SconsDeps:
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._ordered_deps = []
        self._generator_file = 'SConscript_conan'
        check_using_build_profile(self._conanfile)

    @property
    def ordered_deps(self):
        if not self._ordered_deps:
            deps = self._conanfile.dependencies.host.topological_sort
            self._ordered_deps = [dep for dep in reversed(deps.values())]
        return self._ordered_deps

    def _get_cpp_info(self):
        ret = NewCppInfo()
        for dep in self.ordered_deps:
            dep_cppinfo = dep.cpp_info.aggregated_components()
            ret.merge(dep_cppinfo)
        return ret

    def generate(self):
        save(self._generator_file, self._content)

    @property
    def _content(self):
        template = Template("""
        "{{dep}}" : {
            "CPPPATH" : {{info.includedirs}},
            "LIBPATH" : {{info.libdirs}},
            "BINPATH" : {{info.bindirs}},
            "LIBS" : {{info.libs + info.system_libs}},
            "FRAMEWORKS" : {{info.frameworks}},
            "FRAMEWORKPATH" : {{info.frameworkdirs}},
            "CPPDEFINES" : {{info.defines}},
            "CXXFLAGS" : {{info.cxxflags}},
            "CCFLAGS" : {{info.cflags}},
            "SHLINKFLAGS" : {{info.sharedlinkflags}},
            "LINKFLAGS" : {{info.exelinkflags}},
        },
        "{{dep}}_version" : "{{info.version}}",
        """)
        sections = ["conan = {\n"]
        all_flags = template.render(dep="conan", info=self._get_cpp_info())
        sections.append(all_flags)
        host_req = self._conanfile.dependencies.host
        test_req = self._conanfile.dependencies.test
        all_deps = list(host_req.values()) + list(test_req.values())
        for dep in all_deps:
            dep_flags = template.render(dep=dep.ref.name, info=dep.cpp_info)
            sections.append(dep_flags)
        sections.append("}\n")
        sections.append("Return('conan')\n")
        return "\n".join(sections)
