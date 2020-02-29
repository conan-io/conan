
"""
Boost Build Conan Generator

This is a simple project-root.jam generator declaring all conan dependencies
as boost-build lib targets. This lets you link against them in your Jamfile
as a <library> property. Link against the "conant-deps" target.

"""

from conans.model import Generator


def JamfileOutput(dep_cpp_info):
    out = ''
    for lib in dep_cpp_info.libs:
        out += 'lib %s :\n' % lib
        out += '\t: # requirements\n'
        out += '\t<name>%s\n' % lib
        out += ''.join('\t<search>%s\n' % x.replace("\\", "/") for x in dep_cpp_info.lib_paths)
        out += '\t: # default-build\n'
        out += '\t: # usage-requirements\n'
        out += ''.join('\t<define>%s\n' % x for x in dep_cpp_info.defines)
        out += ''.join('\t<include>%s\n' % x.replace("\\", "/") for x in dep_cpp_info.include_paths)
        out += ''.join('\t<cxxflags>%s\n' % x for x in dep_cpp_info.cxxflags)
        out += ''.join('\t<cflags>%s\n' % x for x in dep_cpp_info.cflags)
        out += ''.join('\t<ldflags>%s\n' % x for x in dep_cpp_info.sharedlinkflags)
        out += '\t;\n\n'
    return out


class BoostBuildGenerator(Generator):
    @property
    def filename(self):
        return "project-root.jam"

    @property
    def content(self):
        out = ''

        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            out += JamfileOutput(dep_cpp_info)

        out += 'alias conan-deps :\n'
        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            for lib in dep_cpp_info.libs:
                out += '\t%s\n' % lib
        out += ';\n'

        return out

