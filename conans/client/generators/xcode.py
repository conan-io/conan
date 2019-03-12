from conans.model import Generator
from conans.paths import BUILD_INFO_XCODE


class XCodeGenerator(Generator):

    template = '''
HEADER_SEARCH_PATHS = $(inherited) {include_dirs}
LIBRARY_SEARCH_PATHS = $(inherited) {lib_dirs}
OTHER_LDFLAGS = $(inherited) {linker_flags} {libs}

GCC_PREPROCESSOR_DEFINITIONS = $(inherited) {definitions}
OTHER_CFLAGS = $(inherited) {c_compiler_flags}
OTHER_CPLUSPLUSFLAGS = $(inherited) {cxx_compiler_flags}
FRAMEWORK_SEARCH_PATHS = $(inherited) {rootpaths}
'''

    def __init__(self, conanfile):
        super(XCodeGenerator, self).__init__(conanfile)
        deps_cpp_info = conanfile.deps_cpp_info
        self.include_dirs = " ".join('"%s"' % p.replace("\\", "/")
                                     for p in deps_cpp_info.include_paths)
        self.lib_dirs = " ".join('"%s"' % p.replace("\\", "/")
                                 for p in deps_cpp_info.lib_paths)
        self.libs = " ".join(['-l%s' % lib for lib in deps_cpp_info.libs])
        self.definitions = " ".join('"%s"' % d for d in deps_cpp_info.defines)
        self.c_compiler_flags = " ".join(deps_cpp_info.cflags)
        self.cxx_compiler_flags = " ".join(deps_cpp_info.cxxflags)
        self.linker_flags = " ".join(deps_cpp_info.sharedlinkflags)
        self.rootpaths = " ".join('"%s"' % d.replace("\\", "/") for d in deps_cpp_info.rootpaths)

    @property
    def filename(self):
        return BUILD_INFO_XCODE

    @property
    def content(self):
        return self.template.format(**self.__dict__)
