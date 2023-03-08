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
PREMAKE_TEMPLATE_CONF = """
include "{premake_varfile}"
function conan_setup_build_{pkgname}{config}()
{conf_consume_build}
end
function conan_setup_link_{pkgname}{config}()
{conf_consume_link}
end
function conan_setup_{pkgname}{config}()
    conan_setup_build_{pkgname}{config}()
    conan_setup_link_{pkgname}{config}()
end
"""
PREMAKE_TEMPLATE_CONF_BUILD = """
includedirs{{conan_includedirs_{pkgname}{config}}}
bindirs{{conan_bindirs_{pkgname}{config}}}
defines{{conan_defines_{pkgname}{config}}}
"""
PREMAKE_TEMPLATE_CONF_LINK = """
libdirs{{conan_libdirs_{pkgname}{config}}}
links{{conan_libs_{pkgname}{config}}}
links{{conan_system_libs_{pkgname}{config}}}
links{{conan_frameworks_{pkgname}{config}}}
"""
PREMAKE_TEMPLATE_PKG = """
function conan_setup_build_{pkgname}()
{pkg_filter_expand_build}
end
function conan_setup_link_{pkgname}()
{pkg_filter_expand_link}
end
function conan_setup_{pkgname}()
    conan_setup_build_{pkgname}()
    conan_setup_link_{pkgname}()
end
"""
PREMAKE_TEMPLATE_ROOT = """
function conan_setup_build()
{root_call_all_build}
end
function conan_setup_link()
{root_call_all_link}
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
    
    def _premake_filtered_fallback(self, content, configurations, architecture, indent=1):
        """
        - Uses filters that serve the same purpose than ``_premake_filtered()``
        - This call will create an inverse filter on configurations. It will only apply if non of the 
          ``configurations`` from this function call is present in premake. This is the fallback when a premake
          configuration is NOT named like one of the conan build_type(s).
        """
        fallback_filter = ", ".join(
            [f'"configurations:not {configuration}"' for configuration in configurations]
        )
        lines = list(itertools.chain.from_iterable([cnt.splitlines() for cnt in content]))
        return [
            # Set new filter
            f'{self.tab * indent}filter {{ {fallback_filter}, "architecture:{architecture}" }}',
            # Emit content
            *[f"{self.tab * indent}{self.tab}{line.strip()}" for line in list(filter(None, lines))],
            # Clear active filter
            f"{self.tab * indent}filter {{}}",
        ]
    
    def _premake_pkg_expand(self, configurations, architectures, profiles, 
                            callback_profile, callback_architecture):
        return "\n".join([
            *["\n".join(self._premake_filtered(callback_profile(profile), profile[2], 
                profile[3], indent=1)) for profile in profiles],
            *["\n".join(self._premake_filtered_fallback(callback_architecture(architecture), 
                configurations, architecture, indent=1)) for architecture in architectures]
        ])

    @property
    def content(self):
        check_duplicated_generator(self, self._conanfile)
        
        self.output_files = {}
        conf_suffix = self._config_suffix()
        
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
        for require, dep in full_req:
            dep_name = require.ref.name
            dep_names.append(dep_name)

            # Convert and aggregate dependency's
            dep_cppinfo = dep.cpp_info.copy()
            dep_cppinfo.set_relative_base_folder(dep.package_folder)
            dep_aggregate = dep_cppinfo.aggregated_components()
            
            # Generate config dependent package variable and setup premake file
            var_filename = PREMAKE_VAR_FILE.format(pkgname=dep_name, config=conf_suffix)
            conf_filename = PREMAKE_CONF_FILE.format(pkgname=dep_name, config=conf_suffix)
            self._output_lua_file(var_filename, [
                PREMAKE_TEMPLATE_VAR.format(pkgname=dep_name, 
                    config=conf_suffix, deps=_PremakeTemplate(dep_aggregate))
            ])
            self._output_lua_file(conf_filename, [
                PREMAKE_TEMPLATE_CONF.format(
                    pkgname=dep_name, config=conf_suffix, premake_varfile=var_filename,
                    conf_consume_build=self._indent_string(
                        PREMAKE_TEMPLATE_CONF_BUILD.format(pkgname=dep_name, config=conf_suffix)
                    ),
                    conf_consume_link=self._indent_string(
                        PREMAKE_TEMPLATE_CONF_LINK.format(pkgname=dep_name, config=conf_suffix)
                    )
                )
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
            configurations = [profile[2] for profile in profiles]
            architectures = list(dict.fromkeys([profile[3] for profile in profiles]))

            # Fallback configuration (when user defined config is unknown -> prefer release or last)
            fallback_configuration = "release"
            if "release" not in configurations and len(configurations) > 0: 
                fallback_configuration = configurations[-1]
            
            # Emit package premake file
            pkg_files.append(PREMAKE_PKG_FILE.format(pkgname=dep_name))
            self._output_lua_file(pkg_files[-1], [
                # Includes
                *['include "{}"'.format(profile[0]) for profile in profiles],
                # Functions
                PREMAKE_TEMPLATE_PKG.format(pkgname=dep_name, 
                    pkg_filter_expand_build=self._premake_pkg_expand(
                        configurations, architectures, profiles, 
                        lambda profile: [
                            PREMAKE_TEMPLATE_CONF_BUILD.format(
                                pkgname=dep_name, config=f"_{profile[1]}"
                            )
                        ], 
                        lambda architecture: [
                            PREMAKE_TEMPLATE_CONF_BUILD.format(
                                pkgname=dep_name, config=f"_{fallback_configuration}_{architecture}"
                            )
                        ]
                    ), 
                    pkg_filter_expand_link=self._premake_pkg_expand(
                        configurations, architectures, profiles, 
                        lambda profile: [
                            PREMAKE_TEMPLATE_CONF_LINK.format(
                                pkgname=dep_name, config=f"_{profile[1]}"
                            )
                        ], 
                        lambda architecture: [
                            PREMAKE_TEMPLATE_CONF_LINK.format(
                                pkgname=dep_name, 
                                config=f"_{fallback_configuration}_{architecture}"
                            )
                        ]
                    ), 
                )
            ])

        # Output global premake file 
        self._output_lua_file(PREMAKE_ROOT_FILE, [
            # Includes
            *[f'include "{pkg_file}"' for pkg_file in pkg_files],
            # Functions
            PREMAKE_TEMPLATE_ROOT.format(
                root_call_all_build="\n".join(
                    [f"{self.tab}conan_setup_build_{dep_name}()" for dep_name in dep_names]
                ), 
                root_call_all_link="\n".join(
                    [f"{self.tab}conan_setup_link_{dep_name}()" for dep_name in dep_names]
                )
            )
        ])

        return self.output_files
