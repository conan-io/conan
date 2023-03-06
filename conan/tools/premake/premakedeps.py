from conan.internal import check_duplicated_generator
from conans.model.build_info import CppInfo
from conans.util.files import save

# Filename format strings
PREMAKE_VAR_FILE = "conan_{pkgname}_vars{config}.premake5.lua"
PREMAKE_CONF_FILE = "conan_{pkgname}{config}.premake5.lua"
PREMAKE_LIB_FILE = "conan_{pkgname}.premake5.lua"
PREMAKE_ROOT_FILE = "conandeps.premake5.lua"

# File template format strings
PREMAKE_TEMPLATE_VAR = """
conan_includedirs_{pkgname}{config} = {{{deps.includedirs}}}
conan_libdirs_{pkgname}{config} = {{{deps.libdirs}}}
conan_bindirs_{pkgname}{config} = {{{deps.bindirs}}}
conan_libs_{pkgname}{config} = {{{deps.libs}}}
conan_system_libs_{pkgname}{config} = {{{deps.system_libs}}}
conan_defines_{pkgname}{config} = {{{deps.defines}}}
conan_cxxflags_{pkgname}{config} = {{{deps.cxxflags}}}
conan_cflags_{pkgname}{config} = {{{deps.cflags}}}
conan_sharedlinkflags_{pkgname}{config} = {{{deps.sharedlinkflags}}}
conan_exelinkflags_{pkgname}{config} = {{{deps.exelinkflags}}}
conan_frameworks_{pkgname}{config} = {{{deps.frameworks}}}
"""
# TODO: Somehow add the correct flags (maybe as subfunctions like "conan_setup_c_...", "conan_setup_cpp_...", "conan_setup_sharedlib_...", "conan_setup_application_...")
PREMAKE_TEMPLATE_CONF = """
include "{PREMAKE_VAR_FILE}"
function conan_setup_build_{pkgname}{config}()
    includedirs{{conan_includedirs_{pkgname}{config}}}
    bindirs{{conan_bindirs_{pkgname}{config}}}
    defines{{conan_defines_{pkgname}{config}}}
end
function conan_setup_link_{pkgname}{config}()
    libdirs{{conan_libdirs_{pkgname}{config}}}
    links{{conan_libs_{pkgname}{config}}}
    links{{conan_system_libs_{pkgname}{config}}}
    links{{conan_frameworks_{pkgname}{config}}}
end
function conan_setup_{pkgname}{config}()
    conan_setup_build_{pkgname}{config}()
    conan_setup_link_{pkgname}{config}()
end
"""
PREMAKE_TEMPLATE_LIB = """
{LIB_ALLCONF_INCLUDES}
function conan_setup_build_{pkgname}()
    {LIB_FILTER_EXPAND_BUILD}
end
function conan_setup_link_{pkgname}()
    {LIB_FILTER_EXPAND_LINK}
end
function conan_setup_{pkgname}()
    conan_setup_build_{pkgname}()
    conan_setup_link_{pkgname}()
end
"""
PREMAKE_TEMPLATE_ROOT = """
{ROOT_ALL_INCLUDES}
function conan_setup_build()

end
function conan_setup_link()

end
function conan_setup()
    conan_setup_build()
    conan_setup_link()
end
"""

# Helper class that expands cpp_info meta information in lua readable string sequences
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

# Main premake5 dependency generator
class PremakeDeps(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        # Return value buffer
        self.output_files = {}
        # Extract configuration and architecture form conanfile
        self.configuration = conanfile.settings.build_type
        self.architecture = conanfile.settings.arch

    def generate(self):
        check_duplicated_generator(self, self._conanfile)
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)

    def _config_suffix(self):
        props = [("Configuration", self.configuration),
                 ("Platform", self.architecture)]
        name = "".join("_%s" % v for _, v in props)
        return name.lower()
    
    def _output_lua_file(self, filename, content):
        self.output_files[filename] = "\n".join(["#!lua", *content])

    @property
    def content(self):
        check_duplicated_generator(self, self._conanfile)
        self.output_files = {}

        # Variables required for generation
        conf_suffix = self._config_suffix()
        host_req = self._conanfile.dependencies.host
        test_req = self._conanfile.dependencies.test
        build_req = self._conanfile.dependencies.build

        # Iterate all the transitive requires
        for require, dep in list(host_req.items()) + list(test_req.items()) + list(build_req.items()):
            dep_name = require.ref.name

            # Convert and aggregate dependency's
            dep_cppinfo = dep.cpp_info.copy()
            dep_cppinfo.set_relative_base_folder(dep.package_folder)
            dep_aggregate = dep_cppinfo.aggregated_components()
            
            # Generate package and config separated files
            var_filename = PREMAKE_VAR_FILE.format(pkgname=dep_name, config=conf_suffix)
            conf_filename = PREMAKE_CONF_FILE.format(pkgname=dep_name, config=conf_suffix)
            self._output_lua_file(var_filename, [
                PREMAKE_TEMPLATE_VAR.format(pkgname=dep_name, config=conf_suffix, deps=_PremakeTemplate(dep_aggregate))
            ])
            self._output_lua_file(conf_filename, [
                PREMAKE_TEMPLATE_CONF.format(pkgname=dep_name, config=conf_suffix, PREMAKE_VAR_FILE=var_filename)
            ])

            # TODO: Output global lib lua file

        # TODO: Output global premake file 

        return self.output_files
