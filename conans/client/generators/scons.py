from conans.model import Generator

class SConsGenerator(Generator):
    @property
    def filename(self):
        return "SConscript_conan"

    @property
    def content(self):
        template = ('    "{dep}" : {{\n'
                    '        "CPPPATH"     : {info.include_paths},\n'
                    '        "LIBPATH"     : {info.lib_paths},\n'
                    '        "BINPATH"     : {info.bin_paths},\n'
                    '        "LIBS"        : {info.libs},\n'
                    '        "CPPDEFINES"  : {info.defines},\n'
                    '        "CXXFLAGS"    : {info.cppflags},\n'
                    '        "CCFLAGS"     : {info.cflags},\n'
                    '        "SHLINKFLAGS" : {info.sharedlinkflags},\n'
                    '        "LINKFLAGS"   : {info.exelinkflags},\n'
                    '    }},\n')

        sections = []
        sections.append("conan = {\n")

        all_flags = template.format(dep="conan", info=self.deps_build_info)
        sections.append(all_flags)

        for dep_name, info in self.deps_build_info.dependencies:
            dep_name = dep_name.replace("-", "_")
            dep_flags = template.format(dep=dep_name, info=info)
            sections.append(dep_flags)

        sections.append("}\n")

        sections.append("Return('conan')\n")

        return "\n".join(sections)
