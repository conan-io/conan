from conans.model import Generator
from conans.paths import BUILD_INFO_QMAKE


class DepsCppQmake(object):
    def __init__(self, deps_cpp_info):

        def multiline(field):
            return " \\\n    ".join('"%s"' % p.replace("\\", "/") for p in field)

        self.include_paths = multiline(deps_cpp_info.include_paths)
        self.lib_paths = " \\\n    ".join('-L"%s"' % p.replace("\\", "/")
                                          for p in deps_cpp_info.lib_paths)
        self.bin_paths = multiline(deps_cpp_info.bin_paths)
        self.res_paths = multiline(deps_cpp_info.res_paths)
        self.build_paths = multiline(deps_cpp_info.build_paths)

        self.libs = " ".join('-l%s' % l for l in deps_cpp_info.libs)
        self.defines = " \\\n    ".join('"%s"' % d for d in deps_cpp_info.defines)
        self.cppflags = " ".join(deps_cpp_info.cppflags)
        self.cflags = " ".join(deps_cpp_info.cflags)
        self.sharedlinkflags = " ".join(deps_cpp_info.sharedlinkflags)
        self.exelinkflags = " ".join(deps_cpp_info.exelinkflags)

        self.rootpath = '%s' % deps_cpp_info.rootpath.replace("\\", "/")


class QmakeGenerator(Generator):
    @property
    def filename(self):
        return BUILD_INFO_QMAKE

    @property
    def content(self):
        deps = DepsCppQmake(self.deps_build_info)

        template = ('CONAN_INCLUDEPATH{dep_name}{build_type} += {deps.include_paths}\n'
                    'CONAN_LIBS{dep_name}{build_type} += {deps.libs}\n'
                    'CONAN_LIBDIRS{dep_name}{build_type} += {deps.lib_paths}\n'
                    'CONAN_BINDIRS{dep_name}{build_type} += {deps.bin_paths}\n'
                    'CONAN_RESDIRS{dep_name}{build_type} += {deps.res_paths}\n'
                    'CONAN_BUILDDIRS{dep_name}{build_type} += {deps.build_paths}\n'
                    'CONAN_DEFINES{dep_name}{build_type} += {deps.defines}\n'
                    'CONAN_QMAKE_CXXFLAGS{dep_name}{build_type} += {deps.cppflags}\n'
                    'CONAN_QMAKE_CFLAGS{dep_name}{build_type} += {deps.cflags}\n'
                    'CONAN_QMAKE_LFLAGS{dep_name}{build_type} += {deps.sharedlinkflags}\n'
                    'CONAN_QMAKE_LFLAGS{dep_name}{build_type} += {deps.exelinkflags}\n')
        sections = []
        template_all = template
        all_flags = template_all.format(dep_name="", deps=deps, build_type="")
        sections.append(all_flags)

        for config, cpp_info in self.deps_build_info.configs.items():
            deps = DepsCppQmake(cpp_info)
            dep_flags = template_all.format(dep_name="", deps=deps,
                                            build_type="_" + str(config).upper())
            sections.append(dep_flags)

        template_deps = template + 'CONAN{dep_name}_ROOT{build_type} = "{deps.rootpath}"\n'

        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            deps = DepsCppQmake(dep_cpp_info)
            dep_flags = template_deps.format(dep_name="_" + dep_name.upper(), deps=deps,
                                             build_type="")
            sections.append(dep_flags)

            for config, cpp_info in dep_cpp_info.configs.items():
                deps = DepsCppQmake(cpp_info)
                dep_flags = template_deps.format(dep_name="_" + dep_name.upper(), deps=deps,
                                                 build_type="_" + str(config).upper())
                sections.append(dep_flags)

        output = "\n".join(sections)
        output += ('\nCONFIG(conan_basic_setup) {\n'
                   '    INCLUDEPATH += $$CONAN_INCLUDEPATH\n'
                   '    LIBS += $$CONAN_LIBS\n'
                   '    QMAKE_LIBDIRS += $$CONAN_LIBDIRS\n'
                   '    BINDIRS += $$CONAN_BINDIRS\n'
                   '    DEFINES += $$CONAN_DEFINES\n'
                   '    QMAKE_CXXFLAGS += $$CONAN_QMAKE_CXXFLAGS\n'
                   '    QMAKE_CFLAGS += $$CONAN_QMAKE_CFLAGS\n'
                   '    QMAKE_LFLAGS += $$CONAN_QMAKE_LFLAGS\n'
                   '    QMAKE_CXXFLAGS_DEBUG += $$CONAN_QMAKE_CXXFLAGS_DEBUG\n'
                   '    QMAKE_CFLAGS_DEBUG += $$CONAN_QMAKE_CFLAGS_DEBUG\n'
                   '    QMAKE_LFLAGS_DEBUG += $$CONAN_QMAKE_LFLAGS_DEBUG\n'
                   '    QMAKE_CXXFLAGS_RELEASE += $$CONAN_QMAKE_CXXFLAGS_RELEASE\n'
                   '    QMAKE_CFLAGS_RELEASE += $$CONAN_QMAKE_CFLAGS_RELEASE\n'
                   '    QMAKE_LFLAGS_RELEASE += $$CONAN_QMAKE_LFLAGS_RELEASE\n'
                   '}\n')

        return output
