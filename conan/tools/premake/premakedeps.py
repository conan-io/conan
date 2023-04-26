import itertools 
import glob
import re

from conan.internal import check_duplicated_generator
from conans.model.build_info import CppInfo
from conans.util.files import save

# Filename format strings
PREMAKE_VAR_FILE = "conan_{pkgname}_vars{config}.premake5.lua"
PREMAKE_CONF_FILE = "conan_{pkgname}{config}.premake5.lua"
PREMAKE_PKG_FILE = "conan_{pkgname}.premake5.lua"
PREMAKE_ROOT_FILE = "conandeps.premake5.lua"

# File template format strings
PREMAKE_TEMPLATE_UTILS = """
function conan_premake_tmerge(dst, src)
    for k, v in pairs(src) do
        if type(v) == "table" then
            if type(conandeps[k] or 0) == "table" then
                conan_premake_tmerge(dst[k] or {}, src[k] or {})
            else
                dst[k] = v
            end
        else
            dst[k] = v
        end
    end
    return dst
end
"""
PREMAKE_TEMPLATE_VAR = """
include "conanutils.premake5.lua"

t_conandeps = {{}}
t_conandeps["{config}"] = {{}}
t_conandeps["{config}"]["{pkgname}"] = {{}}
t_conandeps["{config}"]["{pkgname}"]["includedirs"] = {{{deps.includedirs}}}
t_conandeps["{config}"]["{pkgname}"]["libdirs"] = {{{deps.libdirs}}}
t_conandeps["{config}"]["{pkgname}"]["bindirs"] = {{{deps.bindirs}}}
t_conandeps["{config}"]["{pkgname}"]["libs"] = {{{deps.libs}}}
t_conandeps["{config}"]["{pkgname}"]["system_libs"] = {{{deps.system_libs}}}
t_conandeps["{config}"]["{pkgname}"]["defines"] = {{{deps.defines}}}
t_conandeps["{config}"]["{pkgname}"]["cxxflags"] = {{{deps.cxxflags}}}
t_conandeps["{config}"]["{pkgname}"]["cflags"] = {{{deps.cflags}}}
t_conandeps["{config}"]["{pkgname}"]["sharedlinkflags"] = {{{deps.sharedlinkflags}}}
t_conandeps["{config}"]["{pkgname}"]["exelinkflags"] = {{{deps.exelinkflags}}}
t_conandeps["{config}"]["{pkgname}"]["frameworks"] = {{{deps.frameworks}}}

if conandeps == nil then conandeps = {{}} end
conan_premake_tmerge(conandeps, t_conandeps)
"""
PREMAKE_TEMPLATE_ROOT_BUILD = """
        includedirs(conandeps[conf][pkg]["includedirs"])
        bindirs(conandeps[conf][pkg]["bindirs"])
        defines(conandeps[conf][pkg]["defines"])
"""
PREMAKE_TEMPLATE_ROOT_LINK = """
        libdirs(conandeps[conf][pkg]["libdirs"])
        links(conandeps[conf][pkg]["libs"])
        links(conandeps[conf][pkg]["system_libs"])
        links(conandeps[conf][pkg]["frameworks"])
"""
PREMAKE_TEMPLATE_ROOT_FUNCTION = """
function {function_name}(conf, pkg)
    if conf == nil then
{filter_call}
    elseif pkg == nil then
        for k,v in pairs(conandeps[conf]) do
            {function_name}(conf, k)
        end
    else
{lua_content}
    end
end
"""
PREMAKE_TEMPLATE_ROOT_GLOBAL = """
function conan_setup(conf, pkg)
    conan_setup_build(conf, pkg)
    conan_setup_link(conf, pkg)
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


class PremakeDeps(object):
    """
    PremakeDeps class generator
    conandeps.premake5.lua: unconditional import of all *direct* dependencies only
    """

    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """

        self._conanfile = conanfile

        # Tab configuration
        self.tab = "    "

        # Return value buffer
        self.output_files = {}
        # Extract configuration and architecture form conanfile
        self.configuration = conanfile.settings.build_type
        self.architecture = conanfile.settings.arch

    def generate(self):
        """
        Generates ``conan_<pkg>_vars_<config>.premake5.lua``, ``conan_<pkg>_<config>.premake5.lua``,
        and ``conan_<pkg>.premake5.lua`` files into the ``conanfile.generators_folder``.
        """

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

    def _indent_string(self, string, indent=1):
        return "\n".join([
            f"{self.tab * indent}{line}" for line in list(filter(None, string.splitlines()))
        ])
    
    def _premake_filtered(self, content, configuration, architecture, indent=0):
        """
        - Surrounds the lua line(s) contained within ``content`` with a premake "filter" and returns the result.
        - A "filter" will affect all premake function calls after it's set. It's used to limit following project 
          setup function call(s) to a certain scope. Here it is used to limit the calls in content to only apply
          if the premake ``configuration`` and ``architecture`` matches the parameters in this function call.
        """
        lines = list(itertools.chain.from_iterable([cnt.splitlines() for cnt in content]))
        return [
            # Set new filter
            f'{self.tab * indent}filter {{ "configurations:{configuration}", "architecture:{architecture}" }}',
            # Emit content
            *[f"{self.tab * indent}{self.tab}{line.strip()}" for line in list(filter(None, lines))],
            # Clear active filter
            f"{self.tab * indent}filter {{}}",
        ]

    @property
    def content(self):
        check_duplicated_generator(self, self._conanfile)
        
        self.output_files = {}
        conf_suffix = str(self._config_suffix())
        conf_name = conf_suffix[1::]
        
        # Global utility file
        self._output_lua_file("conanutils.premake5.lua", [PREMAKE_TEMPLATE_UTILS])

        # Extract all dependencies
        host_req = self._conanfile.dependencies.host
        test_req = self._conanfile.dependencies.test
        build_req = self._conanfile.dependencies.build

        # Merge into one list
        full_req = list(host_req.items()) \
                   + list(test_req.items()) \
                   + list(build_req.items())

        # Process dependencies and accumulate globally required data
        pkg_files = []
        dep_names = []
        config_sets = []
        for require, dep in full_req:
            dep_name = require.ref.name
            dep_names.append(dep_name)

            # Convert and aggregate dependency's
            dep_cppinfo = dep.cpp_info.copy()
            dep_cppinfo.set_relative_base_folder(dep.package_folder)
            dep_aggregate = dep_cppinfo.aggregated_components()
            
            # Generate config dependent package variable and setup premake file
            var_filename = PREMAKE_VAR_FILE.format(pkgname=dep_name, config=conf_suffix)
            self._output_lua_file(var_filename, [
                PREMAKE_TEMPLATE_VAR.format(pkgname=dep_name, 
                    config=conf_name, deps=_PremakeTemplate(dep_aggregate))
            ])

            # Create list of all available profiles by searching on disk
            file_pattern = PREMAKE_VAR_FILE.format(pkgname=dep_name, config="_*")
            file_regex = PREMAKE_VAR_FILE.format(pkgname=re.escape(dep_name), config="_(([^_]*)_(.*))")
            available_files = glob.glob(file_pattern)
            # Add filename of current generations var file if not already present
            if var_filename not in available_files:
                available_files.append(var_filename)
            profiles = [
                (regex_res[0], regex_res.group(1), regex_res.group(2), regex_res.group(3)) for regex_res in [
                    re.search(file_regex, file_name) for file_name in available_files
                ]
            ]
            config_sets = [profile[1] for profile in profiles]

            # Emit package premake file
            pkg_filename = PREMAKE_PKG_FILE.format(pkgname=dep_name)
            pkg_files.append(pkg_filename)
            self._output_lua_file(pkg_filename, [
                # Includes
                *['include "{}"'.format(profile[0]) for profile in profiles],
            ])

        # Output global premake file 
        self._output_lua_file(PREMAKE_ROOT_FILE, [
            # Includes
            *[f'include "{pkg_file}"' for pkg_file in pkg_files],
            # Functions
            PREMAKE_TEMPLATE_ROOT_FUNCTION.format(
                function_name="conan_setup_build", 
                lua_content=PREMAKE_TEMPLATE_ROOT_BUILD, 
                filter_call="\n".join(
                    ["\n".join(self._premake_filtered(
                        [f'conan_setup_build("{config}")'], config.split("_", 1)[0], config.split("_", 1)[1], 2)
                    ) for config in config_sets]
                )
            ),
            PREMAKE_TEMPLATE_ROOT_FUNCTION.format(
                function_name="conan_setup_link", 
                lua_content=PREMAKE_TEMPLATE_ROOT_LINK, 
                filter_call="\n".join(
                    ["\n".join(self._premake_filtered(
                        [f'conan_setup_link("{config}")'], config.split("_", 1)[0], config.split("_", 1)[1], 2)
                    ) for config in config_sets]
                )
            ),
            PREMAKE_TEMPLATE_ROOT_GLOBAL
        ])

        return self.output_files
