from conans.model import Generator
from conans.paths import BUILD_INFO


class DepsCppTXT(object):
    def __init__(self, deps_cpp_info):
        self.include_paths = "\n".join(p.replace("\\", "/")
                                       for p in deps_cpp_info.include_paths)
        self.lib_paths = "\n".join(p.replace("\\", "/")
                                   for p in deps_cpp_info.lib_paths)
        self.res_paths = "\n".join(p.replace("\\", "/")
                                   for p in deps_cpp_info.res_paths)
        self.build_paths = "\n".join(p.replace("\\", "/")
                                     for p in deps_cpp_info.build_paths)
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
        template = ('[includedirs{dep}{config}]\n{deps.include_paths}\n\n'
                    '[libdirs{dep}{config}]\n{deps.lib_paths}\n\n'
                    '[bindirs{dep}{config}]\n{deps.bin_paths}\n\n'
                    '[resdirs{dep}{config}]\n{deps.res_paths}\n\n'
                    '[builddirs{dep}{config}]\n{deps.build_paths}\n\n'
                    '[libs{dep}{config}]\n{deps.libs}\n\n'
                    '[defines{dep}{config}]\n{deps.defines}\n\n'
                    '[cppflags{dep}{config}]\n{deps.cppflags}\n\n'
                    '[cflags{dep}{config}]\n{deps.cflags}\n\n'
                    '[sharedlinkflags{dep}{config}]\n{deps.sharedlinkflags}\n\n'
                    '[exelinkflags{dep}{config}]\n{deps.exelinkflags}\n\n')

        sections = []
        deps = DepsCppTXT(self.deps_build_info)
        all_flags = template.format(dep="", deps=deps, config="")
        sections.append(all_flags)

        for config, cpp_info in self.deps_build_info.configs.items():
            deps = DepsCppTXT(cpp_info)
            all_flags = template.format(dep="", deps=deps, config=":" + config)
            sections.append(all_flags)

        template_deps = template + '[rootpath{dep}]\n{deps.rootpath}\n\n'

        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            dep = "_" + dep_name
            deps = DepsCppTXT(dep_cpp_info)
            dep_flags = template_deps.format(dep=dep, deps=deps, config="")
            sections.append(dep_flags)

            for config, cpp_info in dep_cpp_info.configs.items():
                deps = DepsCppTXT(cpp_info)
                all_flags = template.format(dep=dep, deps=deps, config=":" + config)
                sections.append(all_flags)

        return "\n".join(sections)
