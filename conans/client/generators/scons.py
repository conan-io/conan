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
                    '        "LIBS"        : {libs},\n'
                    '        "FRAMEWORKS"  : {info.frameworks},\n'
                    '        "FRAMEWORKPATH"  : {info.framework_paths},\n'
                    '        "CPPDEFINES"  : {info.defines},\n'
                    '        "CXXFLAGS"    : {info.cxxflags},\n'
                    '        "CCFLAGS"     : {info.cflags},\n'
                    '        "SHLINKFLAGS" : {info.sharedlinkflags},\n'
                    '        "LINKFLAGS"   : {info.exelinkflags},\n'
                    '    }},\n'
                    '    "{dep}_version" : "{info.version}",\n')

        sections = ["conan = {\n"]

        libs = self.deps_build_info.libs + self.deps_build_info.system_libs
        all_flags = template.format(dep="conan", info=self.deps_build_info, libs=libs)
        sections.append(all_flags)

        for config, cpp_info in self.deps_build_info.configs.items():
            libs = cpp_info.libs + cpp_info.system_libs
            all_flags = template.format(dep="conan:" + config, info=cpp_info, libs=libs)
            sections.append(all_flags)

        for dep_name, info in self.deps_build_info.dependencies:
            dep_name = dep_name.replace("-", "_")
            libs = info.libs + info.system_libs
            dep_flags = template.format(dep=dep_name, info=info, libs=libs)
            sections.append(dep_flags)

            for config, cpp_info in info.configs.items():
                libs = cpp_info.libs + cpp_info.system_libs
                all_flags = template.format(dep=dep_name + ":" + config, info=cpp_info, libs=libs)
                sections.append(all_flags)

        sections.append("}\n")

        sections.append("Return('conan')\n")

        return "\n".join(sections)
