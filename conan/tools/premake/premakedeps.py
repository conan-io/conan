from conan.internal import check_duplicated_generator
from conans.model.build_info import CppInfo
from conans.util.files import save

PREMAKE_FILE = "conandeps.premake5.lua"


# Helper class that expands cpp_info meta information in lua readable string sequences
class _PremakeTemplate(object):
    def __init__(self, dep_cpp_info):
        def _format_paths(paths):
            if not paths:
                return ""
            return ",\n".join(f'"{p}"'.replace("\\", "/") for p in paths)

        def _format_flags(flags):
            if not flags:
                return ""
            return ", ".join('"%s"' % p.replace('"', '\\"') for p in flags)

        self.includedirs = _format_paths(dep_cpp_info.includedirs)
        self.libdirs = _format_paths(dep_cpp_info.libdirs)
        self.bindirs = _format_paths(dep_cpp_info.bindirs)
        self.libs = _format_flags(dep_cpp_info.libs)
        self.system_libs = _format_flags(dep_cpp_info.system_libs)
        self.defines = _format_flags(dep_cpp_info.defines)
        self.cxxflags = _format_flags(dep_cpp_info.cxxflags)
        self.cflags = _format_flags(dep_cpp_info.cflags)
        self.sharedlinkflags = _format_flags(dep_cpp_info.sharedlinkflags)
        self.exelinkflags = _format_flags(dep_cpp_info.exelinkflags)
        self.frameworks = ", ".join('"%s.framework"' % p.replace('"', '\\"') for p in
                                    dep_cpp_info.frameworks) if dep_cpp_info.frameworks else ""
        self.sysroot = f"{dep_cpp_info.sysroot}".replace("\\", "/") \
            if dep_cpp_info.sysroot else ""


class PremakeDeps(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def generate(self):
        check_duplicated_generator(self, self._conanfile)
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)

    @property
    def content(self):
        # Extract all dependencies
        host_req = self._conanfile.dependencies.host
        test_req = self._conanfile.dependencies.test
        build_req = self._conanfile.dependencies.build

        # Merge into one list
        full_req = list(host_req.items()) \
                   + list(test_req.items()) \
                   + list(build_req.items())

        all_cpp_info = CppInfo()

        # merge all dependencies
        for require, dep in full_req:
            all_cpp_info.merge(dep.cpp_info.aggregated_components())

        ret = {}  # filename -> file content

        template = ('conan_includedirs = {{{deps.includedirs}}}\n'
                    'conan_libdirs = {{{deps.libdirs}}}\n'
                    'conan_bindirs = {{{deps.bindirs}}}\n'
                    'conan_libs = {{{deps.libs}}}\n'
                    'conan_system_libs = {{{deps.system_libs}}}\n'
                    'conan_defines = {{{deps.defines}}}\n'
                    'conan_cxxflags = {{{deps.cxxflags}}}\n'
                    'conan_cflags = {{{deps.cflags}}}\n'
                    'conan_sharedlinkflags = {{{deps.sharedlinkflags}}}\n'
                    'conan_exelinkflags = {{{deps.exelinkflags}}}\n'
                    'conan_frameworks = {{{deps.frameworks}}}\n')

        sections = ["#!lua"]

        sections.extend(
            ['conan_build_type = "{0}"'.format(str(self._conanfile.settings.build_type)),
            'conan_arch = "{0}"'.format(str(self._conanfile.settings.get_safe("arch"))),
            ""])

        deps = _PremakeTemplate(all_cpp_info)
        all_flags = template.format(deps=deps)
        sections.append(all_flags)
        sections.append(
            "function conan_setup()\n"
            "    configurations{conan_build_type}\n"
            "    architecture(conan_arch)\n"
            "    includedirs{conan_includedirs}\n"
            "    libdirs{conan_libdirs}\n"
            "    links{conan_libs}\n"
            "    links{conan_system_libs}\n"
            "    links{conan_frameworks}\n"
            "    defines{conan_defines}\n"
            "    bindirs{conan_bindirs}\n"
            "    buildoptions{conan_cflags}\n"
            "    buildoptions{conan_cxxflags}\n"
            "    linkoptions{conan_sharedlinkflags}\n"
            "    linkoptions{conan_exelinkflags}\n"
            "end\n")
        ret[PREMAKE_FILE] = "\n".join(sections)

        return ret
