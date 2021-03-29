import os
import textwrap

from conans.errors import ConanException
from conans.model.build_info import DepCppInfo
from conans.util.files import load, save

VALID_LIB_EXTENSIONS = (".so", ".lib", ".a", ".dylib", ".bc")


class PremakeDeps(object):
    
    _vars_conf_props = textwrap.dedent("""\
       {lua_module}.conan_includedirs{name} = {{{include_dirs}}}
       {lua_module}.conan_libdirs{name} = {{{lib_dirs}}}
       {lua_module}.conan_bindirs{name} = {{{bin_dirs}}}
       {lua_module}.conan_libs{name} = {{{libs}}}
       {lua_module}.conan_system_libs{name} = {{{system_libs}}}
       {lua_module}.conan_defines{name} = {{{definitions}}}
       {lua_module}.conan_cxxflags{name} = {{{compiler_flags}}}
       {lua_module}.conan_cflags{name} = {{{compiler_flags}}}
       {lua_module}.conan_sharedlinkflags{name} = {{{linker_flags}}}
       {lua_module}.conan_exelinkflags{name} = {{{linker_flags}}}
       """)

    _vars_luafile = textwrap.dedent("""\
        local {lua_module} = {{}}

        {lua_module}.conan_build_type = "{build_type}"
        {lua_module}.conan_arch = "{arch}"

        {deps}

        function {lua_module}.conan_basic_setup()
            configurations{{{lua_module}.conan_build_type}}
            architecture({lua_module}.conan_arch)
            includedirs{{{lua_module}.conan_includedirs}}
            libdirs{{{lua_module}.conan_libdirs}}
            links{{{lua_module}.conan_libs}}
            links{{{lua_module}.conan_system_libs}}
            defines{{{lua_module}.conan_defines}}
            bindirs{{{lua_module}.conan_bindirs}}
        end
        
        return {lua_module}
        """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.configuration = conanfile.settings.build_type
        self.arch = conanfile.settings.arch
        self.output_path = os.getcwd()

    def generate(self):
        if self.configuration is None:
            raise ConanException("PremakeDeps.configuration is None, it should have a value")

        self._lua_module = "conan_{config}".format(config=str(self.configuration).lower())

        generator_files = self._content()
        for generator_file, content in generator_files.items():
            generator_file = os.path.join(self.output_path, generator_file)
            save(generator_file, content)

    def _pkg_props(self, name, cpp_info):
        def add_valid_ext(libname):
            (base, ext) = os.path.splitext(libname)
            return libname if ext == 'framework' else base

        fields = {
            'name': name,
            'lua_module': self._lua_module,
            'root_folder': cpp_info.rootpath,
            'bin_dirs': ";".join('"%s"' % p for p in cpp_info.bin_paths),
            #'res_dirs': ";".join('"%s"' % p for p in cpp_info.res_paths),
            'include_dirs': ";".join('"%s"' % p for p in cpp_info.include_paths),
            'lib_dirs': ";".join('"%s"' % p for p in cpp_info.lib_paths),
            'libs': ";".join('"%s"' % add_valid_ext(lib) for lib in cpp_info.libs),
            'system_libs': ";".join('"%s"' % add_valid_ext(sys_dep) for sys_dep in cpp_info.system_libs),
            'definitions': ";".join('"%s"' % d for d in cpp_info.defines),
            'compiler_flags': " ".join(cpp_info.cxxflags + cpp_info.cflags),
            'linker_flags': " ".join(cpp_info.sharedlinkflags),
            'exe_flags': " ".join(cpp_info.exelinkflags),
        }
        formatted_template = self._vars_conf_props.format(**fields)
        return formatted_template

    def _content(self):
        
        deps = []
        deps.append(self._pkg_props("", self._conanfile.deps_cpp_info))

        for dep in self._conanfile.dependencies.host_requires:
            cpp_info = DepCppInfo(dep.cpp_info)
            deps.append(self._pkg_props("_{}".format(dep.name), cpp_info))

        fields = {
            'lua_module': self._lua_module,
            'build_type': self.configuration,
            'arch': self.arch,
            'deps': "\n".join(deps),
        }

        filename = str(self.configuration).lower()
        formatted_template = self._vars_luafile.format(**fields)
        
        return {
            "conanbuildinfo_{}.premake.lua".format(filename): formatted_template
        }