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


def get_package_name(req):
    ret = req.cpp_info.get_property("pkg_config_name", "PkgConfigDeps")
    return ret or req.ref.name


def get_component_name(req, comp_name):
    if comp_name not in req.cpp_info.components:
        # foo::foo might be referencing the root cppinfo
        if req.ref.name == comp_name:
            return get_package_name(req)
        raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                             "package requirement".format(name=req.ref.name, cname=comp_name))
    ret = req.cpp_info.components[comp_name].get_property("pkg_config_name", "PkgConfigDeps")
    return ret or comp_name


class PkgConfigDeps(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile

    @staticmethod
    def _get_pc_name(pkg_name, comp_name):
        """Build a composed name for all the components and its package root name"""
        return "%s-%s" % (pkg_name, comp_name)

    def _get_requires_names(self, name, cpp_info):
        """
        Get all the pkg-config valid names from the requires ones given a dependency and
        a CppInfo object.

        Note: CppInfo could be coming from one Component object instead of the dependency
        """
        ret = []
        for req in cpp_info.requires:
            pkg_name, comp_name = req.split("::") if "::" in req else (name, req)
            # FIXME: it could allow defining requires to not direct dependencies
            req_conanfile = self._conanfile.dependencies.host[pkg_name]
            comp_alias_name = get_component_name(req_conanfile, comp_name)
            ret.append(self._get_pc_name(pkg_name, comp_alias_name))
        return ret

    def get_components_files_and_content(self, dep):
        """Get all the *.pc files content for the dependency and each of its components"""
        pc_files = {}
        pkg_name = get_package_name(dep)
        comp_names = []
        pc_gen = _PCFilesTemplate(self._conanfile, dep)
        # Loop through all the package's components
        for comp_name, comp_cpp_info in dep.cpp_info.get_sorted_components().items():
            comp_name = get_component_name(dep, comp_name)
            comp_names.append(comp_name)
            # FIXME: this str(dep.ref.name) is only needed for python2.7 (unicode values).
            #        Remove it for Conan 2.0
            comp_requires_names = self._get_requires_names(str(dep.ref.name), comp_cpp_info)
            # Get the *.pc file content for each component
            pkg_comp_name = self._get_pc_name(pkg_name, comp_name)
            pc_files.update(pc_gen.get_pc_filename_and_content(comp_requires_names,
                                                               name=pkg_comp_name,
                                                               cpp_info=comp_cpp_info))
        # Let's create a *.pc file for the main package
        pkg_requires = [self._get_pc_name(pkg_name, i) for i in comp_names]
        pc_files.update(pc_gen.get_wrapper_pc_filename_and_content(pkg_requires))
        return pc_files

    @property
    def content(self):
        """Get all the *.pc files content"""
        pc_files = {}
        host_req = self._conanfile.dependencies.host
        for require, dep in host_req.items():
            if dep.cpp_info.has_components:
                pc_files.update(self.get_components_files_and_content(dep))
            else:  # Content for package without components
                pc_gen = _PCFilesTemplate(self._conanfile, dep)
                # FIXME: this str(dep.ref.name) is only needed for python2.7 (unicode values).
                #        Remove it for Conan 2.0
                requires = self._get_requires_names(str(dep.ref.name), dep.cpp_info)
                pc_files.update(pc_gen.get_pc_filename_and_content(requires))
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
        self._name = get_package_name(dep)

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

    def get_pc_filename_and_content(self, requires, name=None, cpp_info=None):

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

        dep_name = name or self._name
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
            "name": dep_name,
            "description": self._conanfile.description or "Conan package: %s" % dep_name,
            "version": version,
            "requires": requires,
            "cpp_info": cpp_info,
            "gnudeps_flags": GnuDepsFlags(self._conanfile, cpp_info)
        }
        template = Template(self.pc_file_template, trim_blocks=True, lstrip_blocks=True,
                            undefined=StrictUndefined)
        return {dep_name + ".pc": template.render(context)}

    def get_wrapper_pc_filename_and_content(self, requires, name=None):
        dep_name = name or self._name
        context = {
            "name": dep_name,
            "description": self._conanfile.description or "Conan package: %s" % dep_name,
            "version": self._dep.ref.version,
            "requires": requires
        }
        template = Template(self.wrapper_pc_file_template, trim_blocks=True, lstrip_blocks=True,
                            undefined=StrictUndefined)
        return {dep_name + ".pc": template.render(context)}
