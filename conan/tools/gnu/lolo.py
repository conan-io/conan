"""
    PkgConfigDeps Conan generator

    - PC FILE EXAMPLE:

        prefix=/usr
        exec_prefix=${prefix}
        libdir=${exec_prefix}/lib
        includedir=${prefix}/include

        Name: my-project
        Description: Some brief but informative description
        Version: 1.2.3
        Libs: -L${libdir} -lmy-project-1 -linkerflag -Wl,-rpath=${libdir}
        Cflags: -I${includedir}/my-project-1
        Requires: glib-2.0 >= 2.40 gio-2.0 >= 2.42 nice >= 0.1.6
        Requires.private: gthread-2.0 >= 2.40
"""
import os
import textwrap

from jinja2 import Template, StrictUndefined

from conan.tools.gnu.gnudeps_flags import GnuDepsFlags
from conans.errors import ConanException
from conans.util.files import save


def get_package_reference_name(dep):
    """Get the reference name for the given package"""
    # FIXME: this str(dep.ref.name) is only needed for python2.7 (unicode values).
    #        Remove it for Conan 2.0
    return str(dep.ref.name)


class PkgConfigDeps(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._out = self._conanfile.output
        # pkg_config_name could be a list of names so let's save all the names as alias
        # for instance, set_property("pkg_config_name", ["target1", "alias1", "alias2"])
        self._global_pkg_config_name_aliases = list()
        self._pkg_config_name_aliases = dict()

    def _get_pkg_config_name(self, info_obj):
        """
        Get the property pkg_config_name given by a CppInfo or _NewComponent object and
        save all the possible aliases defined for that name.

        :param info_obj: <_NewComponent> or <_CppInfo> object
        :return: str or None
        """
        aliases = info_obj.get_property("pkg_config_name", "PkgConfigDeps")
        # if it's a list of names, let's save the other ones as pure aliases
        if isinstance(aliases, list):
            # The main pkg_config_name is the first one
            pkg_config_name = aliases[0]
            aliases = aliases[1:]
            if aliases:
                self._pkg_config_name_aliases[pkg_config_name] = aliases
                # Loop over the aliases defined to check any possible duplication
                for alias in aliases:
                    if alias in self._global_pkg_config_name_aliases:
                        self._out.warn("Alias name '%s' was already defined by any other package or "
                                       "component and it'll be overwritten." % alias)
                    else:
                        self._global_pkg_config_name_aliases.append(alias)
        else:
            pkg_config_name = aliases
        return pkg_config_name

    def get_package_name(self, dep):
        """
        If user declares the property "pkg_config_name" as part of the global cpp_info,
        it'll be used as a complete alias for that package.
        """
        return self._get_pkg_config_name(dep.cpp_info) or get_package_reference_name(dep)

    def get_component_name(self, dep, comp_name):
        """
        If user declares the property "pkg_config_name" as part of the cpp_info.components["comp_name"],
        it'll be used as a complete alias for that package component.
        """
        if comp_name not in dep.cpp_info.components:
            raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                                 "package requirement".format(name=get_package_reference_name(dep),
                                                              cname=comp_name))
        return self._get_pkg_config_name(dep.cpp_info.components[comp_name])

    @staticmethod
    def _get_pc_name(pkg_name, comp_name):
        """Build a composed name for all the components and its package root name"""
        return "%s-%s" % (pkg_name, comp_name)

    def _get_component_requires_names(self, dep_name, cpp_info, dep=None):
        """
        Get all the pkg-config valid names from the requires ones given a dependency and
        a CppInfo object.

        Note: CppInfo could be coming from one Component object instead of the dependency
        """
        ret = []
        for req in cpp_info.requires:
            pkg_name, comp_name = req.split("::") if "::" in req else (dep_name, req)
            # FIXME: it could allow defining requires to not direct dependencies
            req_conanfile = self._conanfile.dependencies.host[pkg_name]
            breakpoint()
            comp_alias_name = self.get_component_name(req_conanfile, comp_name)
            if not comp_alias_name:
                # Just in case, let's be sure about the pkg has any alias
                pkg_name = self.get_package_name(req_conanfile)
                comp_alias_name = self._get_pc_name(pkg_name, comp_name)
            ret.append(comp_alias_name)
        return ret

    def _get_requires_names(self, dep):
        """Get all the dependency's requirements (public dependencies and components)"""
        dep_name = get_package_reference_name(dep)
        # At first, let's check if we have defined some component requires, e.g., "pkg::cmp1"
        requires = self._get_component_requires_names(dep_name, dep.cpp_info, dep=dep)
        # If we have found some component requires it would be enough
        if not requires:
            # If no requires were found, let's try to get all the direct dependencies,
            # e.g., requires = "other_pkg/1.0"
            requires = [self.get_package_name(req) for req in dep.dependencies.direct_host.values()]
        return requires

    def _get_aliases_files_and_content(self, dep):
        """Get all the *.pc files content for the aliases defined previously"""
        pc_files = {}
        for pkg_config_name, aliases in self._pkg_config_name_aliases.items():
            for alias in aliases:
                pc_file = _PCFilesTemplate.get_wrapper_pc_filename_and_content(
                    [pkg_config_name],
                    alias,
                    description="Alias %s for %s" % (alias, pkg_config_name),
                    version=dep.ref.version
                )
                pc_files.update(pc_file)
        return pc_files

    def _get_components_files_and_content(self, dep):
        """Get all the *.pc files content for the dependency and each of its components"""
        pc_files = {}
        pkg_name = self.get_package_name(dep)
        pkg_comp_names = []
        pc_gen = _PCFilesTemplate(self._conanfile, dep)
        # Loop through all the package's components
        for comp_name, comp_cpp_info in dep.cpp_info.get_sorted_components().items():
            comp_requires_names = self._get_component_requires_names(get_package_reference_name(dep),
                                                                     comp_cpp_info, dep=dep)
            pkg_comp_name = self.get_component_name(dep, comp_name)
            if not pkg_comp_name:
                pkg_comp_name = self._get_pc_name(pkg_name, comp_name)
            pkg_comp_names.append(pkg_comp_name)
            # Get the *.pc file content for each component
            pc_files.update(pc_gen.get_pc_filename_and_content(comp_requires_names,
                                                               name=pkg_comp_name,
                                                               cpp_info=comp_cpp_info))
        # Let's create a *.pc file for the main package
        pc_files.update(pc_gen.get_wrapper_pc_filename_and_content(pkg_comp_names,
                                                                   pkg_name,
                                                                   description=self._conanfile.description,
                                                                   version=dep.ref.version))
        return pc_files

    @property
    def content(self):
        """Get all the *.pc files content"""
        pc_files = {}
        host_req = self._conanfile.dependencies.host
        for _, dep in host_req.items():
            # Restart the aliases cache per dependency
            self._pkg_config_name_aliases = dict()

            if dep.cpp_info.has_components:
                pc_files.update(self._get_components_files_and_content(dep))
            else:  # Content for package without components
                pc_gen = _PCFilesTemplate(self._conanfile, dep)
                requires = self._get_requires_names(dep)
                name = self.get_package_name(dep)
                pc_files.update(pc_gen.get_pc_filename_and_content(requires, name))
            # Save all the created alias if any
            pc_files.update(self._get_aliases_files_and_content(dep))

        return pc_files

    def generate(self):
        """Save all the *.pc files"""
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)


class _PCFilesTemplate(object):

    def __init__(self, conanfile, dep):
        self._conanfile = conanfile
        self._dep = dep

    pc_file_template = textwrap.dedent("""\

    {%- macro get_libs(libdirs, cpp_info, gnudeps_flags) -%}
    {%- for _ in libdirs -%}
    {{ '-L"${libdir%s}"' % loop.index + " " }}
    {%- endfor -%}
    {%- for sys_lib in (cpp_info.libs + cpp_info.system_libs) -%}
    {{ "-l%s" % sys_lib + " " }}
    {%- endfor -%}
    {%- for shared_flag in (cpp_info.sharedlinkflags + cpp_info.exelinkflags) -%}
    {{  shared_flag + " " }}
    {%- endfor -%}
    {%- for _ in libdirs -%}
    {%- set flag = gnudeps_flags._rpath_flags(["${libdir%s}" % loop.index]) -%}
    {%- if flag|length -%}
    {{ flag[0] + " " }}
    {%- endif -%}
    {%- endfor -%}
    {%- for framework in (gnudeps_flags.frameworks + gnudeps_flags.framework_paths) -%}
    {{ framework + " " }}
    {%- endfor -%}
    {%- endmacro -%}

    {%- macro get_cflags(includedirs, cpp_info) -%}
    {%- for _ in includedirs -%}
    {{ '-I"${includedir%s}"' % loop.index + " " }}
    {%- endfor -%}
    {%- for cxxflags in cpp_info.cxxflags -%}
    {{ cxxflags + " " }}
    {%- endfor -%}
    {%- for cflags in cpp_info.cflags-%}
    {{ cflags + " " }}
    {%- endfor -%}
    {%- for define in cpp_info.defines-%}
    {{  "-D%s" % define + " " }}
    {%- endfor -%}
    {%- endmacro -%}

    prefix={{ prefix_path }}
    {% for path in libdirs %}
    {{ "libdir{}={}".format(loop.index, path) }}
    {% endfor %}
    {% for path in includedirs %}
    {{ "includedir%d=%s" % (loop.index, path) }}
    {% endfor %}
    {% if pkg_config_custom_content %}
    # Custom PC content
    {{ pkg_config_custom_content }}
    {% endif %}

    Name: {{ name }}
    Description: {{ description }}
    Version: {{ version }}
    Libs: {{ get_libs(libdirs, cpp_info, gnudeps_flags) }}
    Cflags: {{ get_cflags(includedirs, cpp_info) }}
    {% if requires|length %}
    Requires: {{ requires|join(' ') }}
    {% endif %}
    """)

    wrapper_pc_file_template = textwrap.dedent("""\
    Name: {{ name }}
    Description: {{ description }}
    Version: {{ version }}
    {% if requires|length %}
    Requires: {{ requires|join(' ') }}
    {% endif %}
    """)

    def get_pc_filename_and_content(self, requires, name, cpp_info=None):

        def get_formatted_dirs(folders, prefix_path_):
            ret = []
            for i, directory in enumerate(folders):
                directory = os.path.normpath(directory).replace("\\", "/")
                prefix = ""
                if not os.path.isabs(directory):
                    prefix = "${prefix}/"
                elif directory.startswith(prefix_path_):
                    prefix = "${prefix}/"
                    directory = os.path.relpath(directory, prefix_path_).replace("\\", "/")
                ret.append("%s%s" % (prefix, directory))
            return ret

        package_folder = self._dep.package_folder
        version = self._dep.ref.version
        cpp_info = cpp_info or self._dep.cpp_info

        prefix_path = package_folder.replace("\\", "/")
        libdirs = get_formatted_dirs(cpp_info.libdirs, prefix_path)
        includedirs = get_formatted_dirs(cpp_info.includedirs, prefix_path)

        context = {
            "prefix_path": prefix_path,
            "libdirs": libdirs,
            "includedirs": includedirs,
            "pkg_config_custom_content": cpp_info.get_property("pkg_config_custom_content", "PkgConfigDeps"),
            "name": name,
            "description": self._conanfile.description or "Conan package: %s" % name,
            "version": version,
            "requires": requires,
            "cpp_info": cpp_info,
            "gnudeps_flags": GnuDepsFlags(self._conanfile, cpp_info)
        }
        template = Template(self.pc_file_template, trim_blocks=True, lstrip_blocks=True,
                            undefined=StrictUndefined)
        return {name + ".pc": template.render(context)}

    @staticmethod
    def get_wrapper_pc_filename_and_content(requires, name, description=None, version=None):
        context = {
            "name": name,
            "description": description or "Conan package: %s" % name,
            "version": version,
            "requires": requires
        }
        template = Template(_PCFilesTemplate.wrapper_pc_file_template, trim_blocks=True,
                            lstrip_blocks=True, undefined=StrictUndefined)
        return {name + ".pc": template.render(context)}
