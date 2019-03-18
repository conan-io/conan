from conans.model import Generator
from conans.paths import BUILD_INFO_PREMAKE


class PremakeDeps(object):

    def __init__(self, deps_cpp_info):
        self.include_paths = ",\n".join('"%s"' % p.replace("\\", "/")
                                        for p in deps_cpp_info.include_paths)
        self.lib_paths = ",\n".join('"%s"' % p.replace("\\", "/")
                                    for p in deps_cpp_info.lib_paths)
        self.bin_paths = ",\n".join('"%s"' % p.replace("\\", "/")
                                    for p in deps_cpp_info.bin_paths)
        self.libs = ", ".join('"%s"' % p for p in deps_cpp_info.libs)
        self.defines = ", ".join('"%s"' % p for p in deps_cpp_info.defines)
        self.cxxflags = ", ".join('"%s"' % p for p in deps_cpp_info.cxxflags)
        self.cflags = ", ".join('"%s"' % p for p in deps_cpp_info.cflags)
        self.sharedlinkflags = ", ".join('"%s"' % p for p in deps_cpp_info.sharedlinkflags)
        self.exelinkflags = ", ".join('"%s"' % p for p in deps_cpp_info.exelinkflags)

        self.rootpath = "%s" % deps_cpp_info.rootpath.replace("\\", "/")


class PremakeGenerator(Generator):
    @property
    def filename(self):
        return BUILD_INFO_PREMAKE

    @property
    def content(self):
        deps = PremakeDeps(self.deps_build_info)

        template = ('conan_includedirs{dep} = {{{deps.include_paths}}}\n'
                    'conan_libdirs{dep} = {{{deps.lib_paths}}}\n'
                    'conan_bindirs{dep} = {{{deps.bin_paths}}}\n'
                    'conan_libs{dep} = {{{deps.libs}}}\n'
                    'conan_defines{dep} = {{{deps.defines}}}\n'
                    'conan_cxxflags{dep} = {{{deps.cxxflags}}}\n'
                    'conan_cflags{dep} = {{{deps.cflags}}}\n'
                    'conan_sharedlinkflags{dep} = {{{deps.sharedlinkflags}}}\n'
                    'conan_exelinkflags{dep} = {{{deps.exelinkflags}}}\n')

        sections = ["#!lua"]
        
        sections.extend(
                ['conan_build_type = "{0}"'.format(str(self.settings.get_safe("build_type"))),
                 'conan_arch = "{0}"'.format(str(self.settings.get_safe("arch"))),
                 ""]
        )

        all_flags = template.format(dep="", deps=deps)
        sections.append(all_flags)
        template_deps = template + 'conan_rootpath{dep} = "{deps.rootpath}"\n'

        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            deps = PremakeDeps(dep_cpp_info)
            dep_name = dep_name.replace("-", "_")
            dep_flags = template_deps.format(dep="_" + dep_name, deps=deps)
            sections.append(dep_flags)

        sections.append(
            "function conan_basic_setup()\n"
            "    configurations{conan_build_type}\n"
            "    architecture(conan_arch)\n"
            "    includedirs{conan_includedirs}\n"
            "    libdirs{conan_libdirs}\n"
            "    links{conan_libs}\n"
            "    defines{conan_defines}\n"
            "    bindirs{conan_bindirs}\n"
            "end\n")

        return "\n".join(sections)
