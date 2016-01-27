from conans.model import Generator
from conans.paths import BUILD_INFO


class DepsCppTXT(object):
    def __init__(self, deps_cpp_info):
        self.include_paths = "\n".join(p.replace("\\", "/")
                                       for p in deps_cpp_info.include_paths)
        self.lib_paths = "\n".join(p.replace("\\", "/")
                                   for p in deps_cpp_info.lib_paths)
        self.libs = "\n".join(deps_cpp_info.libs)
        self.defines = "\n".join(deps_cpp_info.defines)
        self.cppflags = "\n".join(deps_cpp_info.cppflags)
        self.cflags = "\n".join(deps_cpp_info.cflags)
        self.sharedlinkflags = "\n".join(deps_cpp_info.sharedlinkflags)
        self.exelinkflags = "\n".join(deps_cpp_info.exelinkflags)
        self.bin_paths = "\n".join(p.replace("\\", "/")
                                   for p in deps_cpp_info.bin_paths)
        self.rootpath = "%s" % deps_cpp_info.rootpath.replace("\\", "/")


class TXTGenerator(Generator):
    @property
    def filename(self):
        return BUILD_INFO

    @property
    def content(self):
        deps = DepsCppTXT(self.deps_build_info)

        template = ('[includedirs{dep}]\n{deps.include_paths}\n\n'
                    '[libdirs{dep}]\n{deps.lib_paths}\n\n'
                    '[bindirs{dep}]\n{deps.bin_paths}\n\n'
                    '[libs{dep}]\n{deps.libs}\n\n'
                    '[defines{dep}]\n{deps.defines}\n\n'
                    '[cppflags{dep}]\n{deps.cppflags}\n\n'
                    '[cflags{dep}]\n{deps.cflags}\n\n'
                    '[sharedlinkflags{dep}]\n{deps.sharedlinkflags}\n\n'
                    '[exelinkflags{dep}]\n{deps.exelinkflags}\n\n')

        sections = []
        all_flags = template.format(dep="", deps=deps)
        sections.append(all_flags)
        template_deps = template + '[rootpath{dep}]\n{deps.rootpath}\n\n'

        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            deps = DepsCppTXT(dep_cpp_info)
            dep_flags = template_deps.format(dep="_" + dep_name, deps=deps)
            sections.append(dep_flags)

        return "\n".join(sections)
