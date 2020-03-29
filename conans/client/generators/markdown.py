from jinja2 import Template
import textwrap
from conans.model import Generator
from conans.client.graph.graph import RECIPE_VIRTUAL


requirement_tpl = Template(textwrap.dedent("""
    # {{ name }}/{{ cpp_info.version }}

    ---
    **Note.-** If this package belongs to ConanCenter, you can find more information [here](https://conan.io/center/{{ name }}/{{ cpp_info.version }}/).

    ---

    Information for consumers:

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

    Read below how to use this package using different
    [generators](https://docs.conan.io/en/latest/reference/generators.html). In order to use
    these generators they have to be listed in the _conanfile.py_ file or using the command
    line ``--generator/-g`` in the ``conan install`` command.


    ## ``cmake`` generator

    Add these lines to your *CMakeLists.txt*

    ```cmake
    include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
    conan_basic_setup(TARGETS)

    target_link_libraries(<library_name> {{ cpp_info.get_name("cmake") }}::{{ name }})
    ```


    ## ``cmake_find_package`` generator
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


"""))


class MarkdownGenerator(Generator):

    @property
    def filename(self):
        pass

    @property
    def content(self):
        ret = {}
        for name, cpp_info in self.conanfile.deps_cpp_info.dependencies:
            ret["{}.md".format(name)] = requirement_tpl.render(
                name=name,
                cpp_info=cpp_info
            )
        return ret
