import textwrap

from jinja2 import Template

from conans.model import Generator


class SConsGenerator(Generator):
    @property
    def filename(self):
        return "SConscript_conan"

    @property
    def content(self):
        template = textwrap.dedent("""\
            "{{dep}}" : {
                "CPPPATH"     : {{info.include_paths}},
                "LIBPATH"     : {{info.lib_paths}},
                "BINPATH"     : {{info.bin_paths}},
                {% set libs = info.libs + info.system_libs -%}
                "LIBS"        : [{% if libs %}'{{ libs|join("', '") }}'{% endif %}],
                "FRAMEWORKS"  : {{info.frameworks}},
                "FRAMEWORKPATH"  : {{info.framework_paths}},
                "CPPDEFINES"  : {{info.defines}},
                "CXXFLAGS"    : {{info.cxxflags}},
                "CCFLAGS"     : {{info.cflags}},
                "SHLINKFLAGS" : {{info.sharedlinkflags}},
                "LINKFLAGS"   : {{info.exelinkflags}},
            },
            "{{dep}}_version" : "{{info.version}}",
            """)
        # Nice nested indent
        template = "\n".join("    " + line for line in template.splitlines())
        template = Template(template)

        sections = ["conan = {\n"]

        all_flags = template.render(dep="conan", info=self.deps_build_info)
        sections.append(all_flags)

        for config, cpp_info in self.deps_build_info.configs.items():
            all_flags = template.render(dep="conan:" + config, info=cpp_info)
            sections.append(all_flags)

        for dep_name, info in self.deps_build_info.dependencies:
            dep_name = dep_name.replace("-", "_")
            dep_flags = template.render(dep=dep_name, info=info)
            sections.append(dep_flags)

            for config, cpp_info in info.configs.items():
                all_flags = template.render(dep=dep_name + ":" + config, info=cpp_info)
                sections.append(all_flags)

        sections.append("}\n")

        sections.append("Return('conan')\n")

        return "\n".join(sections)
