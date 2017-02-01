import os
from conans.model import Generator

class AapGenerator(Generator):
    @property
    def filename(self):
        return 'conanbuildinfo.aap'

    @property
    def content(self):
        all_libraries = [os.path.join(foler,lib) for foler in self.deps_build_info.lib_paths for lib in self.deps_build_info.libs]
        existing_libs = filter(lambda x: any(os.path.exists(file) for file in [x + ext for ext in ['.lib', '.a', '.so']]), all_libraries)

        content = \
            'INCLUDE += %s\n' \
            'LIBS += %s\n' \
            'DEFINE += %s\n' \
            'CPPFLAGS += %s\n' \
            'CFLAGS += %s\n' \
            'SHLINKFLAGS += %s\n' \
            'LDFLAGS += %s\n' % (
            ' '.join('-I' + x for x in self.deps_build_info.include_paths),
            ' '.join('-l' + x for x in existing_libs),
            ' '.join('-D' + x for x in self.deps_build_info.defines),
            ' '.join(self.deps_build_info.cppflags),
            ' '.join(self.deps_build_info.cflags),
            ' '.join(self.deps_build_info.sharedlinkflags),
            ' '.join(self.deps_build_info.exelinkflags))

        return content
