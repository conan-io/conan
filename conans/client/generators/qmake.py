from conans.model import Generator


BUILD_INFO_QMAKE = 'conanbuildinfo.pri'


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

        self.libs = " ".join('-l%s' % lib for lib in cpp_info.libs)
        self.system_libs = " ".join('-l%s' % lib for lib in cpp_info.system_libs)
        self.frameworks = " ".join('-framework %s' % framework for framework in cpp_info.frameworks)
        self.framework_paths = " ".join('-F%s' % framework_path for framework_path in
                                        cpp_info.framework_paths)
        self.defines = " \\\n    ".join('"%s"' % d for d in cpp_info.defines)
        self.cxxflags = " ".join(cpp_info.cxxflags)
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
                    'CONAN_SYSTEMLIBS{dep_name}{build_type} += {deps.system_libs}\n'
                    'CONAN_FRAMEWORKS{dep_name}{build_type} += {deps.frameworks}\n'
                    'CONAN_FRAMEWORK_PATHS{dep_name}{build_type} += {deps.framework_paths}\n'
                    'CONAN_LIBDIRS{dep_name}{build_type} += {deps.lib_paths}\n'
                    'CONAN_BINDIRS{dep_name}{build_type} += {deps.bin_paths}\n'
                    'CONAN_RESDIRS{dep_name}{build_type} += {deps.res_paths}\n'
                    'CONAN_BUILDDIRS{dep_name}{build_type} += {deps.build_paths}\n'
                    'CONAN_DEFINES{dep_name}{build_type} += {deps.defines}\n'
                    'CONAN_QMAKE_CXXFLAGS{dep_name}{build_type} += {deps.cxxflags}\n'
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
            dep_name = "_" + dep_name.upper().replace("-", "_").replace(".", "_")
            deps = DepsCppQmake(dep_cpp_info)
            dep_flags = template_deps.format(dep_name=dep_name, deps=deps, build_type="")
            sections.append(dep_flags)

            for config, cpp_info in dep_cpp_info.configs.items():
                deps = DepsCppQmake(cpp_info)
                dep_flags = template_deps.format(dep_name=dep_name, deps=deps,
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
        INCLUDEPATH += $$CONAN_INCLUDEPATH_RELEASE
        LIBS += $$CONAN_LIBS_RELEASE
        LIBS += $$CONAN_LIBDIRS_RELEASE
        BINDIRS += $$CONAN_BINDIRS_RELEASE
        DEFINES += $$CONAN_DEFINES_RELEASE
    } else {
        INCLUDEPATH += $$CONAN_INCLUDEPATH_DEBUG
        LIBS += $$CONAN_LIBS_DEBUG
        LIBS += $$CONAN_LIBDIRS_DEBUG
        BINDIRS += $$CONAN_BINDIRS_DEBUG
        DEFINES += $$CONAN_DEFINES_DEBUG
    }
    LIBS += $$CONAN_SYSTEMLIBS
    CONFIG(release, debug|release) {
        LIBS += $$CONAN_SYSTEMLIBS_RELEASE
    } else {
        LIBS += $$CONAN_SYSTEMLIBS_DEBUG
    }
    LIBS += $$CONAN_FRAMEWORKS
    LIBS += $$CONAN_FRAMEWORK_PATHS
    CONFIG(release, debug|release) {
        LIBS += $$CONAN_FRAMEWORKS_RELEASE
        LIBS += $$CONAN_FRAMEWORK_PATHS_RELEASE
    } else {
        LIBS += $$CONAN_FRAMEWORKS_DEBUG
        LIBS += $$CONAN_FRAMEWORK_PATHS_DEBUG
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
