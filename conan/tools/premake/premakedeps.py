from conan.internal import check_duplicated_generator
from conans.model.build_info import CppInfo
from conans.util.files import save

PREMAKE_FILE = "conandeps.premake.lua"


class _PremakeTemplate(object):
    def __init__(self, deps_cpp_info):
        self.includedirs = ",\n".join('"%s"' % p.replace("\\", "/")
                                      for p in
                                      deps_cpp_info.includedirs) if deps_cpp_info.includedirs else ""
        self.libdirs = ",\n".join('"%s"' % p.replace("\\", "/")
                                  for p in deps_cpp_info.libdirs) if deps_cpp_info.libdirs else ""
        self.bindirs = ",\n".join('"%s"' % p.replace("\\", "/")
                                  for p in deps_cpp_info.bindirs) if deps_cpp_info.bindirs else ""
        self.libs = ", ".join(
            '"%s"' % p.replace('"', '\\"') for p in deps_cpp_info.libs) if deps_cpp_info.libs else ""
        self.system_libs = ", ".join('"%s"' % p.replace('"', '\\"') for p in
                                     deps_cpp_info.system_libs) if deps_cpp_info.system_libs else ""
        self.defines = ", ".join('"%s"' % p.replace('"', '\\"') for p in
                                 deps_cpp_info.defines) if deps_cpp_info.defines else ""
        self.cxxflags = ", ".join(
            '"%s"' % p for p in deps_cpp_info.cxxflags) if deps_cpp_info.cxxflags else ""
        self.cflags = ", ".join(
            '"%s"' % p for p in deps_cpp_info.cflags) if deps_cpp_info.cflags else ""
        self.sharedlinkflags = ", ".join('"%s"' % p.replace('"', '\\"') for p in
                                         deps_cpp_info.sharedlinkflags) \
            if deps_cpp_info.sharedlinkflags else ""
        self.exelinkflags = ", ".join('"%s"' % p.replace('"', '\\"') for p in
                                      deps_cpp_info.exelinkflags) \
            if deps_cpp_info.exelinkflags else ""
        self.frameworks = ", ".join('"%s.framework"' % p.replace('"', '\\"') for p in
                                    deps_cpp_info.frameworks) if deps_cpp_info.frameworks else ""
        self.sysroot = "%s" % deps_cpp_info.sysroot.replace("\\",
                                                            "/") if deps_cpp_info.sysroot else ""


class PremakeDeps(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def generate(self):
        check_duplicated_generator(self, self._conanfile)
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)

    def _get_cpp_info(self):
        ret = CppInfo()
        for dep in self._conanfile.dependencies.host.values():
            dep_cppinfo = dep.cpp_info.copy()
            dep_cppinfo.set_relative_base_folder(dep.package_folder)
            # In case we have components, aggregate them, we do not support isolated "targets"
            dep_cppinfo.aggregate_components()
            ret.merge(dep_cppinfo)
        return ret

    @property
    def content(self):
        ret = {}  # filename -> file content

        host_req = self._conanfile.dependencies.host
        test_req = self._conanfile.dependencies.test

        template = ('conan_includedirs{dep} = {{{deps.includedirs}}}\n'
                    'conan_libdirs{dep} = {{{deps.libdirs}}}\n'
                    'conan_bindirs{dep} = {{{deps.bindirs}}}\n'
                    'conan_libs{dep} = {{{deps.libs}}}\n'
                    'conan_system_libs{dep} = {{{deps.system_libs}}}\n'
                    'conan_defines{dep} = {{{deps.defines}}}\n'
                    'conan_cxxflags{dep} = {{{deps.cxxflags}}}\n'
                    'conan_cflags{dep} = {{{deps.cflags}}}\n'
                    'conan_sharedlinkflags{dep} = {{{deps.sharedlinkflags}}}\n'
                    'conan_exelinkflags{dep} = {{{deps.exelinkflags}}}\n'
                    'conan_frameworks{dep} = {{{deps.frameworks}}}\n')

        sections = ["#!lua"]

        deps = _PremakeTemplate(self._get_cpp_info())
        all_flags = template.format(dep="", deps=deps)
        sections.append(all_flags)
        sections.append(
            "function conan_basic_setup()\n"
            "    configurations{conan_build_type}\n"
            "    architecture(conan_arch)\n"
            "    includedirs{conan_includedirs}\n"
            "    libdirs{conan_libdirs}\n"
            "    links{conan_libs}\n"
            "    links{conan_system_libs}\n"
            "    links{conan_frameworks}\n"
            "    defines{conan_defines}\n"
            "    bindirs{conan_bindirs}\n"
            "end\n")
        ret[PREMAKE_FILE] = "\n".join(sections)

        template_deps = template + 'conan_sysroot{dep} = "{deps.sysroot}"\n'

        # Iterate all the transitive requires
        for require, dep in list(host_req.items()) + list(test_req.items()):
            # FIXME: Components are not being aggregated
            # FIXME: It is not clear the usage of individual dependencies
            deps = _PremakeTemplate(dep.cpp_info)
            dep_name = dep.ref.name.replace("-", "_")
            dep_flags = template_deps.format(dep="_" + dep_name, deps=deps)
            ret[dep.ref.name + '.lua'] = "\n".join(["#!lua", dep_flags])

        return ret
