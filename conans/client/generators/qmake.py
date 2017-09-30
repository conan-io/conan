from conans.model import Generator
from conans.paths import BUILD_INFO_QMAKE


class DepsCppQmake(object):
    def __init__(self, cpp_info):

        def multiline(field):
            return " \\\n    ".join('"%s"' % p.replace("\\", "/") for p in field)

        self.include_paths = multiline(cpp_info.include_paths)
        self.lib_paths = " \\\n    ".join('-L"%s"' % p.replace("\\", "/")
                                          for p in cpp_info.lib_paths)
        self.bin_paths = multiline(cpp_info.bin_paths)
        self.res_paths = multiline(cpp_info.res_paths)
        self.build_paths = multiline(cpp_info.build_paths)

        self.libs = " ".join('-l%s' % l for l in cpp_info.libs)
        self.defines = " \\\n    ".join('"%s"' % d for d in cpp_info.defines)
        self.cppflags = " ".join(cpp_info.cppflags)
        self.cflags = " ".join(cpp_info.cflags)
        self.sharedlinkflags = " ".join(cpp_info.sharedlinkflags)
        self.exelinkflags = " ".join(cpp_info.exelinkflags)

        self.rootpath = '%s' % cpp_info.rootpath.replace("\\", "/")


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
        output += ("""\nCONFIG(conan_basic_setup) {
    INCLUDEPATH += $$CONAN_INCLUDEPATH
    LIBS += $$CONAN_LIBS
    LIBS += $$CONAN_LIBDIRS
    BINDIRS += $$CONAN_BINDIRS
    DEFINES += $$CONAN_DEFINES
    CONFIG(release, debug|release) {
        message("Release config")
        INCLUDEPATH += $$CONAN_INCLUDEPATH_RELEASE
        LIBS += $$CONAN_LIBS_RELEASE
        LIBS += $$CONAN_LIBDIRS_RELEASE
        BINDIRS += $$CONAN_BINDIRS_RELEASE
        DEFINES += $$CONAN_DEFINES_RELEASE
    } else {
        message("Debug config")
        INCLUDEPATH += $$CONAN_INCLUDEPATH_DEBUG
        LIBS += $$CONAN_LIBS_DEBUG
        LIBS += $$CONAN_LIBDIRS_DEBUG
        BINDIRS += $$CONAN_BINDIRS_DEBUG
        DEFINES += $$CONAN_DEFINES_DEBUG
    }
    QMAKE_CXXFLAGS += $$CONAN_QMAKE_CXXFLAGS
    QMAKE_CFLAGS += $$CONAN_QMAKE_CFLAGS
    QMAKE_LFLAGS += $$CONAN_QMAKE_LFLAGS
    QMAKE_CXXFLAGS_DEBUG += $$CONAN_QMAKE_CXXFLAGS_DEBUG
    QMAKE_CFLAGS_DEBUG += $$CONAN_QMAKE_CFLAGS_DEBUG
    QMAKE_LFLAGS_DEBUG += $$CONAN_QMAKE_LFLAGS_DEBUG
    QMAKE_CXXFLAGS_RELEASE += $$CONAN_QMAKE_CXXFLAGS_RELEASE
    QMAKE_CFLAGS_RELEASE += $$CONAN_QMAKE_CFLAGS_RELEASE
    QMAKE_LFLAGS_RELEASE += $$CONAN_QMAKE_LFLAGS_RELEASE
}""")

        return output
