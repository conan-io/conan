from conans.model import Generator
from conans.paths import BUILD_INFO_QMAKE


class DepsCppQmake(object):
    def __init__(self, deps_cpp_info):
        self.include_paths = " \\\n    ".join('"%s"' % p.replace("\\", "/")
                                              for p in deps_cpp_info.include_paths)
        self.lib_paths = " \\\n    ".join('-L"%s"' % p.replace("\\", "/")
                                          for p in deps_cpp_info.lib_paths)
        self.libs = " ".join('-l%s' % l for l in deps_cpp_info.libs)
        self.defines = " \\\n    ".join('"%s"' % d for d in deps_cpp_info.defines)
        self.cppflags = " ".join(deps_cpp_info.cppflags)
        self.cflags = " ".join(deps_cpp_info.cflags)
        self.sharedlinkflags = " ".join(deps_cpp_info.sharedlinkflags)
        self.exelinkflags = " ".join(deps_cpp_info.exelinkflags)
        self.bin_paths = " \\\n    ".join('"%s"' % p.replace("\\", "/")
                                          for p in deps_cpp_info.bin_paths)

        self.rootpath = '%s' % deps_cpp_info.rootpath.replace("\\", "/")


class QmakeGenerator(Generator):
    @property
    def filename(self):
        return BUILD_INFO_QMAKE

    @property
    def content(self):
        deps = DepsCppQmake(self.deps_build_info)

        template = ('CONAN_INCLUDEPATH{dep_name} += {deps.include_paths}\n'
                    'CONAN_LIBS{dep_name} += {deps.lib_paths}\n'
                    'CONAN_BINDIRS{dep_name} += {deps.bin_paths}\n'
                    'CONAN_LIBS{dep_name} += {deps.libs}\n'
                    'CONAN_DEFINES{dep_name} += {deps.defines}\n'
                    'CONAN_QMAKE_CXXFLAGS{dep_name} += {deps.cppflags}\n'
                    'CONAN_QMAKE_CFLAGS{dep_name} += {deps.cflags}\n'
                    'CONAN_QMAKE_LFLAGS{dep_name} += {deps.sharedlinkflags}\n'
                    'CONAN_QMAKE_LFLAGS{dep_name} += {deps.exelinkflags}\n')
        sections = []
        template_all = template
        all_flags = template_all.format(dep_name="", deps=deps)
        sections.append(all_flags)

        template_deps = template + 'CONAN{dep_name}_ROOT = "{deps.rootpath}"\n'

        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            deps = DepsCppQmake(dep_cpp_info)
            dep_flags = template_deps.format(dep_name="_" + dep_name.upper(), deps=deps)
            sections.append(dep_flags)

        output = "\n".join(sections)
        output += ('\nCONFIG(conan_basic_setup) {\n'
                   '    INCLUDEPATH += $$CONAN_INCLUDEPATH\n'
                   '    LIBS += $$CONAN_LIBS\n'
                   '    BINDIRS += $$CONAN_BINDIRS\n'
                   '    LIBS += $$CONAN_LIBS\n'
                   '    DEFINES += $$CONAN_DEFINES\n'
                   '    QMAKE_CXXFLAGS += $$CONAN_QMAKE_CXXFLAGS\n'
                   '    QMAKE_CFLAGS += $$CONAN_QMAKE_CFLAGS\n'
                   '    QMAKE_LFLAGS += $$CONAN_QMAKE_LFLAGS\n'
                   '}\n')

        return output
