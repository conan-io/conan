import os
import textwrap

from jinja2 import DictLoader
from jinja2 import Environment
from conans.model import Generator
import datetime



render_cpp_info = textwrap.dedent("""
    {% macro join_list_sources(items) -%}
    ``{{ "``, ``".join(items) }}``
    {%- endmacro %}

    {% macro render_cpp_info(cpp_info) -%}
    {%- if cpp_info.requires is iterable and cpp_info.requires %}
    * Requires: {{ join_list_sources(cpp_info.requires) }}
    {%- endif %}
    {%- if cpp_info.libs %}
    * Libraries: {{ join_list_sources(cpp_info.libs) }}
    {%- endif %}
    {%- if cpp_info.system_libs %}
    * Systems libs: {{ join_list_sources(cpp_info.system_libs) }}
    {%- endif %}
    {%- if cpp_info.defines %}
    * Preprocessor definitions: {{ join_list_sources(cpp_info.defines) }}
    {%- endif %}
    {%- if cpp_info.cflags %}
    * C_FLAGS: {{ join_list_sources(cpp_info.cflags) }}
    {%- endif %}
    {%- if cpp_info.cxxflags %}
    * CXX_FLAGS: {{ join_list_sources(cpp_info.cxxflags) }}
    {%- endif %}
    {%- endmacro %}
""")

generator_cmake_tpl = textwrap.dedent("""
    ### Generator ``cmake``

    Add these lines to your *CMakeLists.txt*:

    ```cmake
    include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
    conan_basic_setup(TARGETS)

    target_link_libraries(<library_name> CONAN_PKG::{{ cpp_info.get_name("cmake") }})
    ```

    {% set build_modules = cpp_info.build_modules.get('cmake', None) %}
    {% if build_modules %}
    This generator will include some _build modules_:
    {% for bm in build_modules -%}
    * `{{ bm }}`
      ```
      {{ '/'.join([cpp_info.rootpath, bm])|read_pkg_file|indent(width=2) }}
      ```
    {%- endfor -%}
    {%- endif %}
""")

generator_cmake_find_package_tpl = textwrap.dedent("""
    ### Generator ``cmake_find_package``
    {% set cmake_find_package_name = cpp_info.get_name("cmake_find_package") %}
    {% set cmake_find_package_filename = cpp_info.get_filename("cmake_find_package") %}
    Generates the file Find{{ cmake_find_package_filename }}.cmake

    Add these lines to your *CMakeLists.txt*:

    ```cmake
    find_package({{ cmake_find_package_filename }})

    # Use the global target
    target_link_libraries(<library_name> {{ cmake_find_package_name }}::{{ cmake_find_package_name }})
    {% if cpp_info.components %}
    # Or link just one of its components
    {% for cmp_name, cmp_cpp_info in cpp_info.components.items() -%}
    target_link_libraries(<library_name> {{ cmake_find_package_name }}::{{ cmp_cpp_info.get_name("cmake_find_package") }})
    {% endfor %}
    {%- endif %}
    ```

    Remember to adjust your build system settings to match the binaries you are linking with. You can
    use the [CMake build helper](https://docs.conan.io/en/latest/reference/build_helpers/cmake.html) and
    the ``cmake`` generator from a *conanfile.py* or the new [toolchain paradigm](https://docs.conan.io/en/latest/creating_packages/toolchains.html).

    {% set build_modules = cpp_info.build_modules.get('cmake_find_package', None) %}
    {% if build_modules %}
    This generator will include some _build modules_:
    {% for bm in build_modules -%}
    * `{{ bm }}`
      ```
      {{ '/'.join([cpp_info.rootpath, bm])|read_pkg_file|indent(width=2) }}
      ```
    {%- endfor -%}
    {%- endif %}
""")

generator_pkg_config_tpl = textwrap.dedent("""
    ### Generator ``pkg_config``

    This package provides one *pkg-config* file ``{{ cpp_info.get_filename('pkg_config') }}.pc`` with
    all the information from the library
    {% if cpp_info.components -%}
    and another file for each of its components:
    {%- for cmp_name, cmp_cpp_info in cpp_info.components.items() -%}
    ``{{ cmp_cpp_info.get_filename('pkg_config') }}.pc``{% if not loop.last %},{% endif %}
    {%- endfor -%}
    {%- endif -%}.
    Use your *pkg-config* tool as usual to consume the information provided by the Conan package.

    {% set build_modules = cpp_info.build_modules.get('pkg_config', None) %}
    {% if build_modules %}
    This generator will include some _build modules_:
    {% for bm in build_modules -%}
    * `{{ bm }}`
      ```
      {{ '/'.join([cpp_info.rootpath, bm])|read_pkg_file|indent(width=2) }}
      ```
    {%- endfor -%}
    {%- endif %}
""")

requirement_tpl = textwrap.dedent("""
    {% from 'render_cpp_info' import render_cpp_info %}

    # {{ cpp_info.name }}/{{ cpp_info.version }}

    ---
    **Note.-** If this package belongs to ConanCenter, you can find more information [here](https://conan.io/center/{{ cpp_info.name }}/{{ cpp_info.version }}/).

    ---

    {% if requires or required_by %}
    Graph of dependencies:
    {% if requires %}
    * ``{{ cpp_info.name }}`` requires:
        {% for dep_name, dep_cpp_info in requires -%}
        [{{ dep_name }}/{{ dep_cpp_info.version }}]({{ dep_name }}.md){% if not loop.last %}, {% endif %}
        {%- endfor -%}
    {%- endif %}
    {%- if required_by %}
    * ``{{ cpp_info.name }}`` is required by:
        {%- for dep_name, dep_cpp_info in required_by %}
        [{{ dep_name }}/{{ dep_cpp_info.version }}]({{ dep_name }}.md){% if not loop.last %}, {% endif %}
        {%- endfor %}
    {%- endif %}
    {% endif %}

    Information published by ``{{ cpp_info.name }}`` to consumers:

    {%- if cpp_info.includedirs %}
    * Headers (see [below](#header-files))
    {%- endif %}
    {% if cpp_info.components %}
    {% for cmp_name, cmp_cpp_info in cpp_info.components.items() %}
    * Component ``{{ cpp_info.name }}::{{ cmp_name }}``:
    {{ render_cpp_info(cmp_cpp_info)|indent(width=2) }}
    {%- endfor %}
    {% else %}
    {{ render_cpp_info(cpp_info)|indent(width=0) }}
    {% endif %}


    ## Generators

    Read below how to use this package using different
    [generators](https://docs.conan.io/en/latest/reference/generators.html). In order to use
    these generators they have to be listed in the _conanfile.py_ file or using the command
    line argument ``--generator/-g`` in the ``conan install`` command.

    * [``cmake``](#Generator-cmake)
    * [``cmake_find_package``](#Generator-cmake_find_package)
    * [``pkg_config``](#Generator-pkg_config)

    {% include 'generator_cmake' %}
    {% include 'generator_cmake_find_package' %}
    {% include 'generator_pkg_config_tpl' %}

    ---
    ## Header files

    List of header files exposed by this package. Use them in your ``#include`` directives:

    ```cpp
    {%- for header in headers %}
    {{ header }}
    {%- endfor %}
    ```

    ---
    ---
    Conan **{{ conan_version }}**. JFrog LTD. [https://conan.io](https://conan.io). Autogenerated {{ now.strftime('%Y-%m-%d %H:%M:%S') }}.
""")


class MarkdownGenerator(Generator):

    def _list_headers(self, cpp_info):
        rootpath = cpp_info.rootpath
        for include_dir in cpp_info.includedirs:
            for root, _, files in os.walk(os.path.join(cpp_info.rootpath, include_dir)):
                for f in files:
                    yield os.path.relpath(os.path.join(root, f), os.path.join(rootpath, include_dir))

    def _list_requires(self, cpp_info):
        return [(it, self.conanfile.deps_cpp_info[it]) for it in cpp_info.public_deps]

    def _list_required_by(self, cpp_info):
        for other_name, other_cpp_info in self.conanfile.deps_cpp_info.dependencies:
            if cpp_info.name in other_cpp_info.public_deps:
                yield other_name, other_cpp_info

    @property
    def filename(self):
        pass

    @property
    def content(self):
        dict_loader = DictLoader({
            'render_cpp_info': render_cpp_info,
            'package.md': requirement_tpl,
            'generator_cmake': generator_cmake_tpl,
            'generator_cmake_find_package': generator_cmake_find_package_tpl,
            'generator_pkg_config_tpl': generator_pkg_config_tpl,
        })
        env = Environment(loader=dict_loader)
        template = env.get_template('package.md')

        def read_pkg_file(filename):
            try:
                return open(filename, 'r').read()
            except IOError:
                return '# Error reading file content. Please report.'

        env.filters['read_pkg_file'] = read_pkg_file

        from conans import __version__ as conan_version
        ret = {}
        for name, cpp_info in self.conanfile.deps_cpp_info.dependencies:
            ret["{}.md".format(name)] = template.render(
                cpp_info=cpp_info,
                headers=self._list_headers(cpp_info),
                requires=list(self._list_requires(cpp_info)),
                required_by=list(self._list_required_by(cpp_info)),
                conan_version=conan_version,
                now=datetime.datetime.now()
            )
        return ret
