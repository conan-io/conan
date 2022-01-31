import datetime
import os
import textwrap

from jinja2 import DictLoader
from jinja2 import Environment

from conan.tools.cmake.cmakedeps.cmakedeps import CMakeDeps
from conan.tools.cmake.cmakedeps.templates import (
    CMakeDepsFileTemplate,
    get_file_name as cmake_get_file_name)
from conan.tools.gnu.pkgconfigdeps.pc_info_loader import (
    _get_component_name as pkgconfig_get_component_name,
    _get_name_with_namespace as pkgconfig_get_name_with_namespace,
    _get_package_name as pkgconfig_get_package_name
)
from conans.model import Generator


macros = textwrap.dedent("""
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

buildsystem_cmake_tpl = textwrap.dedent("""
    ### CMake

    #### Generator [CMakeToolchain](https://docs.conan.io/en/latest/reference/conanfile/tools/cmake/cmaketoolchain.html)
    `CMakeToolchain` is the toolchain generator for CMake. It will generate a toolchain
    file that can be used in the command-line invocation of CMake with
    `-DCMAKE_TOOLCHAIN_FILE=conantoolchain.cmake`. This generator translates the current
    package configuration, settings, and options, into CMake toolchain syntax.

    #### Generator [CMakeDeps](https://docs.conan.io/en/latest/reference/conanfile/tools/cmake/cmakedeps.html)
    The `CMakeDeps` helper will generate one `xxxx-config.cmake` file per dependency,
    together with other necessary `.cmake` files like version, flags, and directory data
    or configuration.

    If you use it together with the `CMakeToolchain`, these `xxx-config.cmake` files will be found when you run a `find_package()` in your `CMakeLists.txt` file:

    ```
    find_package({{ cmake_variables.file_name }})

    # Use the global target
    target_link_libraries(<target_name> {{ cmake_variables.global_target_name }})

    {% if requirement.cpp_info.has_components %}
    # Or link just one of its components
    {% for component_name, component in requirement.cpp_info.components.items() %}
    {%- if component_name %}
    target_link_libraries(<target_name> {{ cmake_variables.component_alias[component_name] }})
    {%- endif %}
    {%- endfor %}
    {%- endif %}
    ```

    {% set cmake_build_modules = requirement.cpp_info.get_property('cmake_build_modules') %}
    {% if cmake_build_modules %}
    This generator will include some _build modules_:
    {% for bm in cmake_build_modules -%}
    * `{{ relpath(bm, package_folder) | replace("\\\\", "/") }}`
      ```
      {{ bm|read_pkg_file|indent(width=2) }}
      ```
    {%- endfor -%}
    {%- endif %}
""")

buildsystem_vs_tpl = textwrap.dedent("""
    ### Visual Studio

    #### Generator [MSBuildToolchain](https://docs.conan.io/en/latest/reference/conanfile/tools/microsoft.html#msbuildtoolchain)
    `MSBuildToolchain` is the toolchain generator for MSBuild. It translates the current
    package configuration, settings, and options, into a MSBuild properties file that
    you should add to your Visual Sudio solution projects:

    `conantoolchain.props`

    #### Generator [MSBuildDeps](https://docs.conan.io/en/latest/reference/conanfile/tools/microsoft.html#msbuilddeps)
    `MSBuildDeps` is the dependency information generator for Microsoft MSBuild build
    system. It generate a property file with the dependencies of a package ready to be
    used by consumers using MSBuild or Visual Studio.

    Just add the `conandeps.props` file to your solution and projects.
""")

buildsystem_autotools_tpl = textwrap.dedent("""
    ### Autotools

    #### Generator [AutotoolsToolchain](https://docs.conan.io/en/latest/reference/conanfile/tools/gnu/autotoolstoolchain.html)
    `AutotoolsToolchain` is the toolchain generator for Autotools. It will generate
    shell scripts containing environment variable definitions that the autotools build
    system can understand.

    `AutotoolsToolchain` will generate the `conanautotoolstoolchain.sh` or
    `conanautotoolstoolchain.bat` files after a `conan install` command:

    ```
    $ conan install conanfile.py # default is Release
    $ source conanautotoolstoolchain.sh
    # or in Windows
    $ conanautotoolstoolchain.bat
    ```

    If your autotools scripts expect to find dependencies using pkg_config, use the
    `PkgConfigDeps` generator. Otherwise, use `AutotoolsDeps`.

    #### Generator AutotoolsDeps
    The AutotoolsDeps is the dependencies generator for Autotools. It will generate
    shell scripts containing environment variable definitions that the autotools
    build system can understand.

    The AutotoolsDeps will generate after a conan install command the
    conanautotoolsdeps.sh or conanautotoolsdeps.bat files:

    ```
    $ conan install conanfile.py # default is Release
    $ source conanautotoolsdeps.sh
    # or in Windows
    $ conanautotoolsdeps.bat
    ```


    #### Generator PkgConfigDeps
    This package provides one *pkg-config* file ``{{ pkgconfig_variables.pkg_name }}.pc`` with
    all the information from the library
    {% if requirement.cpp_info.has_components %}
    and, if you want to use the components of the library separately, one `.pc` file per component:
    {% for component_name, component in requirement.cpp_info.components.items() %}
    {%- if component_name %}
    ``{{ pkgconfig_variables.component_alias[component_name] }}.pc``{% if not loop.last %},{% endif %}
    {%- endif %}
    {%- endfor %}
    {%- endif %}

    Use your *pkg-config* tool as usual to consume the information provided by the Conan package.
""")

buildsystem_other_tpl = textwrap.dedent("""
    ### Other build systems
    Conan includes generators for [several more build systems](https://docs.conan.io/en/latest/integrations/build_system.html),
    and you can even write [custom integrations](https://docs.conan.io/en/latest/integrations/custom.html)
    if needed.
""")

requirement_tpl = textwrap.dedent("""
    {% from 'macros' import render_cpp_info %}

    # {{ requirement }}

    ---

    ## How to use this recipe

    You can use this recipe with different build systems. For each build system, Conan
    provides different generators that you must list in the `[generators]`section on the
    `conanfile.txt` file, or in the `generators` property of the `conanfile.py`.
    Alternatively, you can use the command line argument  `--generator/-g` in the
    `conan install` command.

    [Here](https://docs.conan.io/en/latest/integrations.html) you can read more about Conan
    integration with several build systems, compilers, IDEs, etc.


    {% if requires or required_by %}
    ## Dependencies
    {% if requires %}
    * ``{{ requirement.ref.name }}`` requires:
        {% for dep_name, dep in requires -%}
        [{{ dep }}]({{ dep_name }}.md){% if not loop.last %}, {% endif %}
        {%- endfor -%}
    {%- endif %}
    {%- if required_by %}
    * ``{{ requirement.ref.name }}`` is required by:
        {%- for dep_name, dep in required_by %}
        [{{ dep }}]({{ dep_name }}.md){% if not loop.last %}, {% endif %}
        {%- endfor %}
    {%- endif %}
    {% endif %}


    ## Build Systems

    {% include 'buildsystem_cmake' %}
    {% include 'buildsystem_vs' %}
    {% include 'buildsystem_autotools' %}
    {% include 'buildsystem_other' %}


    {% if requirement.cpp_info.has_components %}
    ## Declared components

    {%- for component_name, component in requirement.cpp_info.components.items() %}
    {%- if component_name %}
    * Component ``{{ cmake_variables.component_alias[component_name] }}``:

    {{- render_cpp_info(component)|indent(width=2) }}
    {%- endif %}
    {%- endfor %}
    {%- endif %}


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
    def _list_headers(self, requirement):
        for include_dir in requirement.cpp_info.includedirs:
            for root, _, files in os.walk(os.path.join(requirement.package_folder, include_dir)):
                for f in files:
                    yield os.path.relpath(os.path.join(root, f), os.path.join(requirement.package_folder, include_dir))

    def _list_requires(self, requirement):
        return [(dep.ref.name, dep) for dep in requirement.dependencies.host.values()]

    def _list_required_by(self, requirement):
        for dep in self.conanfile.dependencies.host.values():
            name = dep.ref.name
            deps = [dep.ref.name for dep in dep.dependencies.host.values()]

            if requirement.ref.name in deps:
                yield name, dep

    @property
    def filename(self):
        pass

    @property
    def content(self):
        dict_loader = DictLoader({
            'macros': macros,
            'package.md': requirement_tpl,
            'buildsystem_cmake': buildsystem_cmake_tpl,
            'buildsystem_vs': buildsystem_vs_tpl,
            'buildsystem_autotools': buildsystem_autotools_tpl,
            'buildsystem_other': buildsystem_other_tpl
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
        for requirement in self.conanfile.dependencies.host.values():
            cmake_deps = CMakeDeps(self.conanfile)
            cmake_deps_template = CMakeDepsFileTemplate(cmake_deps,
                                                        requirement,
                                                        self.conanfile,
                                                        find_module_mode=False)

            name = requirement.ref.name

            cmake_component_alias = {
                component_name: cmake_deps_template.get_component_alias(requirement, component_name)
                for component_name, _
                in requirement.cpp_info.components.items()
                if component_name
            }
            cmake_variables = {
                'global_target_name': requirement.cpp_info.get_property('cmake_target_name') or "{0}::{0}".format(name),
                'component_alias': cmake_component_alias,
                'file_name': cmake_get_file_name(requirement)
            }

            pkgconfig_component_alias = {
                component_name: pkgconfig_get_component_name(requirement, component_name) or
                                pkgconfig_get_name_with_namespace(pkgconfig_get_package_name(requirement), component_name)
                for component_name, _
                in requirement.cpp_info.components.items()
                if component_name
            }
            pkgconfig_variables = {
                'pkg_name': pkgconfig_get_package_name(requirement),
                'component_alias': pkgconfig_component_alias
            }

            ret["{}.md".format(name)] = template.render(
                requirement=requirement,
                headers=self._list_headers(requirement),
                requires=list(self._list_requires(requirement)),
                required_by=list(self._list_required_by(requirement)),
                cmake_variables=cmake_variables,
                pkgconfig_variables=pkgconfig_variables,
                package_folder=requirement.package_folder,
                relpath = os.path.relpath,
                conan_version=conan_version,
                now=datetime.datetime.now()
            )

        return ret
