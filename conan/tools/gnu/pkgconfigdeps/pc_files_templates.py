import os
import textwrap

from jinja2 import Template, StrictUndefined

from conan.tools.gnu.gnudeps_flags import GnuDepsFlags


def _get_pc_file_template():
    return textwrap.dedent("""\
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


def _get_alias_pc_file_template():
    return textwrap.dedent("""\
        Name: {{ name }}
        Description: {{ description }}
        Version: {{ version }}
        {% if requires|length %}
        Requires: {{ requires|join(' ') }}
        {% endif %}
    """)


def _get_formatted_dirs(folders, prefix_path_):
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


def get_pc_filename_and_content(conanfile, dep, name, requires, description, cpp_info=None):
    package_folder = dep.package_folder
    version = dep.ref.version
    cpp_info = cpp_info or dep.cpp_info

    prefix_path = package_folder.replace("\\", "/")
    libdirs = _get_formatted_dirs(cpp_info.libdirs, prefix_path)
    includedirs = _get_formatted_dirs(cpp_info.includedirs, prefix_path)
    custom_content = cpp_info.get_property("pkg_config_custom_content")

    context = {
        "prefix_path": prefix_path,
        "libdirs": libdirs,
        "includedirs": includedirs,
        "pkg_config_custom_content": custom_content,
        "name": name,
        "description": description,
        "version": version,
        "requires": requires,
        "cpp_info": cpp_info,
        "gnudeps_flags": GnuDepsFlags(conanfile, cpp_info)
    }
    template = Template(_get_pc_file_template(), trim_blocks=True, lstrip_blocks=True,
                        undefined=StrictUndefined)
    return {name + ".pc": template.render(context)}


def get_alias_pc_filename_and_content(dep, name, requires, description):
    context = {
        "name": name,
        "description": description,
        "version": dep.ref.version,
        "requires": requires
    }
    template = Template(_get_alias_pc_file_template(), trim_blocks=True,
                        lstrip_blocks=True, undefined=StrictUndefined)
    return {name + ".pc": template.render(context)}
