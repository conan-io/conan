from jinja2 import Template
import textwrap
import os
from conans.model import Generator
from conans.client.graph.graph import RECIPE_VIRTUAL


requirement_tpl = Template(textwrap.dedent("""
    # {{ name }}/{{ cpp_info.version }}

    ---
    **Note.-** If this package belongs to ConanCenter, you can find more information [here](https://conan.io/center/{{ name }}/{{ cpp_info.version }}/).

    ---

    {% if requires or required_by %}
    Graph of dependencies:
    {% if requires %}
    * ``{{ name }}`` requires:
    {%- for dep_name, dep_cpp_info in requires %}
        [{{ dep_name }}/{{ dep_cpp_info.version }}]({{ dep_name }}.md){% if not loop.last %}, {% endif %}
    {%- endfor %}
    {%- endif %}
    {%- if required_by %}
    * ``{{ name }}`` is required by:
    {%- for dep_name, dep_cpp_info in required_by %}
    [{{ dep_name }}/{{ dep_cpp_info.version }}]({{ dep_name }}.md){% if not loop.last %}, {% endif %}
    {%- endfor %}
    {%- endif %}
    {% endif %}

    Information published by ``{{ name }}`` to consumers:

    {%- if cpp_info.includedirs %}
    * Headers (see [below](#header-files))
    {%- endif%}
    {%- if cpp_info.libs %}
    * Libraries: ``{{ "``, ``".join(cpp_info.libs) }}``
    {%- endif %}
    {%- if cpp_info.system_libs %}
    * Systems libs: ``{{ "``, ``".join(cpp_info.system_libs) }}``
    {%- endif %}
    {%- if cpp_info.defines %}
    * Preprocessor definitions: ``{{ "``, ``".join(cpp_info.defines) }}``
    {%- endif %}
    {%- if cpp_info.cflags %}
    * C_FLAGS: ``{{ "``, ``".join(cpp_info.cflags) }}``
    {%- endif %}
    {%- if cpp_info.cxxflags %}
    * CXX_FLAGS: ``{{ "``, ``".join(cpp_info.cxxflags) }}``
    {%- endif %}
    {%- if cpp_info.build_modules %}
    * Build modules (see [below](#build-modules)): ``{{ "``, ``".join(cpp_info.build_modules) }}``
    {%- endif %}


    ## Generators

    Read below how to use this package using different
    [generators](https://docs.conan.io/en/latest/reference/generators.html). In order to use
    these generators they have to be listed in the _conanfile.py_ file or using the command
    line argument ``--generator/-g`` in the ``conan install`` command.


    ### Generator ``cmake``

    Add these lines to your *CMakeLists.txt*

    ```cmake
    include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
    conan_basic_setup(TARGETS)

    target_link_libraries(<library_name> CONAN_PKG::{{ cpp_info.get_name("cmake") }})
    ```


    ### Generator ``cmake_find_package``
    {% set cmake_find_package_name = cpp_info.get_name("cmake_find_package") %}

    Add these lines to your *CMakeLists.txt*

    ```cmake
    find_package({{ cmake_find_package_name }})

    target_link_libraries(<library_name> {{ cmake_find_package_name }}::{{ cmake_find_package_name }})
    ```

    If you are using the
    [CMake build helper](https://docs.conan.io/en/latest/reference/build_helpers/cmake.html) then
    you need to use the ``cmake`` generator too to adjust the value of CMake variables based on the
    value of Conan ones:

    ```cmake
    include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
    conan_basic_setup(TARGETS)

    find_package({{ cmake_find_package_name }})

    target_link_libraries(<library_name> {{ cmake_find_package_name }}::{{ cmake_find_package_name }})
    ```

    ---
    ## Header files

    List of header files exposed by this package. Use them in your ``#include`` directives:

    ```cpp
    {%- for header in headers %}
    {{ header }}
    {%- endfor %}
    ```

    {%- if cpp_info.build_modules %}
    ---
    ## Build modules

    Modules exported by this recipe. They are automatically included when using Conan generators:

    {% for name, build_module in build_modules %}
    **{{ name }}**
    ```
    {{ build_module }}
    ```
    {% endfor %}
    {% endif %}

"""))


class MarkdownGenerator(Generator):

    def _list_headers(self, cpp_info):
        rootpath = cpp_info.rootpath
        for include_dir in cpp_info.includedirs:
            for root, _, files in os.walk(os.path.join(cpp_info.rootpath, include_dir)):
                for f in files:
                    yield os.path.relpath(os.path.join(root, f), os.path.join(rootpath, include_dir))

    def _list_requires(self, cpp_info):
        return [(it, self.conanfile.deps_cpp_info[it]) for it in cpp_info.public_deps]

    def _list_required_by(self, name):
        for other_name, cpp_info in self.conanfile.deps_cpp_info.dependencies:
            if name in cpp_info.public_deps:
                yield other_name, cpp_info

    def _read_build_modules(self, cpp_info):
        for build_module in cpp_info.build_modules:
            filename = os.path.join(cpp_info.rootpath, build_module)
            yield build_module, open(filename, 'r').read()

    @property
    def filename(self):
        pass

    @property
    def content(self):
        ret = {}
        for name, cpp_info in self.conanfile.deps_cpp_info.dependencies:
            ret["{}.md".format(name)] = requirement_tpl.render(
                name=name,
                cpp_info=cpp_info,
                headers=self._list_headers(cpp_info),
                requires=list(self._list_requires(cpp_info)),
                required_by=list(self._list_required_by(name)),
                build_modules=self._read_build_modules(cpp_info)
            )
        return ret
