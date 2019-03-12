from conans.model import Generator
from conans.paths import BUILD_INFO_QBS


class DepsCppQbs(object):
    def __init__(self, cpp_info):
        delimiter = ",\n                "
        self.include_paths = delimiter.join('"%s"' % p.replace("\\", "/")
                                            for p in cpp_info.include_paths)
        self.lib_paths = delimiter.join('"%s"' % p.replace("\\", "/")
                                        for p in cpp_info.lib_paths)
        self.libs = delimiter.join('"%s"' % l for l in cpp_info.libs)
        self.defines = delimiter.join('"%s"' % d for d in cpp_info.defines)
        self.cxxflags = delimiter.join('"%s"' % d
                                       for d in cpp_info.cxxflags)
        self.cflags = delimiter.join('"%s"' % d for d in cpp_info.cflags)
        linker_flags = cpp_info.sharedlinkflags
        linker_flags.extend(cpp_info.exelinkflags)
        self.linkerFlags = delimiter.join('"%s"' % d for d in linker_flags)
        self.bin_paths = delimiter.join('"%s"' % p.replace("\\", "/")
                                        for p in cpp_info.bin_paths)
        self.rootpath = '%s' % cpp_info.rootpath.replace("\\", "/")


class QbsGenerator(Generator):
    @property
    def filename(self):
        return BUILD_INFO_QBS

    @property
    def content(self):
        deps = DepsCppQbs(self.deps_build_info)

        template = ('    Product {{\n'
                    '        name: "{dep}"\n'
                    '        Export {{\n'
                    '            Depends {{ name: "cpp" }}\n'
                    '            cpp.includePaths: [{deps.include_paths}]\n'
                    '            cpp.libraryPaths: [{deps.lib_paths}]\n'
                    '            cpp.systemIncludePaths: [{deps.bin_paths}]\n'
                    '            cpp.dynamicLibraries: [{deps.libs}]\n'
                    '            cpp.defines: [{deps.defines}]\n'
                    '            cpp.cppFlags: [{deps.cxxflags}]\n'  # TODO: cppFlags -> cxxFlags?
                    '            cpp.cFlags: [{deps.cflags}]\n'
                    '            cpp.linkerFlags: [{deps.linkerFlags}]\n'
                    '        }}\n'
                    '    }}\n')

        sections = []
        all_flags = template.format(dep="ConanBasicSetup", deps=deps)
        sections.append(all_flags)
        template_deps = template + '    // {dep} root path: {deps.rootpath}\n'

        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            deps = DepsCppQbs(dep_cpp_info)
            dep_flags = template_deps.format(dep=dep_name, deps=deps)
            sections.append(dep_flags)

        output = 'import qbs 1.0\n\nProject {\n'
        output += '\n'.join(sections)
        output += '}\n'
        return output
