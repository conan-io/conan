from conans.model import Generator
from conans.paths import BUILD_INFO_QMAKE


class DepsCppQmake(object):
    def __init__(self, deps_cpp_info):
        self.include_paths = " \\\n    ".join('%s' % p.replace("\\", "/")
                                              for p in deps_cpp_info.include_paths)
        self.lib_paths = " \\\n    ".join('-L%s' % p.replace("\\", "/")
                                          for p in deps_cpp_info.lib_paths)
        self.libs = " ".join('-l%s' % l for l in deps_cpp_info.libs)
        self.defines = " \\\n    ".join('"%s"' % d for d in deps_cpp_info.defines)
        self.cppflags = " ".join(deps_cpp_info.cppflags)
        self.cflags = " ".join(deps_cpp_info.cflags)
        self.sharedlinkflags = " ".join(deps_cpp_info.sharedlinkflags)
        self.exelinkflags = " ".join(deps_cpp_info.exelinkflags)
        self.bin_paths = " \\\n    ".join('%s' % p.replace("\\", "/")
                                          for p in deps_cpp_info.bin_paths)

        self.rootpath = '%s' % deps_cpp_info.rootpath.replace("\\", "/")


class QmakeGenerator(Generator):
    @property
    def filename(self):
        return BUILD_INFO_QMAKE

    @property
    def content(self):
        deps = DepsCppQmake(self.deps_build_info)

        template = ('# package{dep} \n\n'
                    'INCLUDEPATH += {deps.include_paths}\n'
                    'LIBS += {deps.lib_paths}\n'
                    'BINDIRS += {deps.bin_paths}\n'
                    'LIBS += {deps.libs}\n'
                    'DEFINES += {deps.defines}\n'
                    'QMAKE_CXXFLAGS += {deps.cppflags}\n'
                    'QMAKE_CFLAGS += {deps.cflags}\n'
                    'QMAKE_LFLAGS += {deps.sharedlinkflags}\n'
                    'QMAKE_LFLAGS += {deps.exelinkflags}\n')

        sections = []
        all_flags = template.format(dep="", deps=deps)
        sections.append(all_flags)
        template_deps = template + 'ROOTPATH{dep} = {deps.rootpath}\n\n'

        for dep_name, dep_cpp_info in self._deps_build_info.dependencies:
            deps = DepsCppQmake(dep_cpp_info)
            dep_flags = template_deps.format(dep="_" + dep_name, deps=deps)
            sections.append(dep_flags)

        return "\n".join(sections)
