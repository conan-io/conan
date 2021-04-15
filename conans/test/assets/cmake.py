import textwrap

from jinja2 import Template


def gen_cmakelists(language="CXX", verify=True, project="project", libname="mylibrary",
                   libsources=None, appname="myapp", appsources=None, cmake_version="3.15"):
    """
    language: C, C++, C/C++
    project: the project name
    """
    cmake = textwrap.dedent("""\
        {% if verify %}
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        set(CMAKE_C_COMPILER_WORKS 1)
        set(CMAKE_C_ABI_COMPILED 1)
        {% endif %}

        cmake_minimum_required(VERSION {{cmake_version}})
        project({{project}} {{language}})

        {% if libsources %}
        add_library({{libname}} {% for s in libsources %} {{s}} {% endfor %})
        {% endif %}

        {% if appsources %}
        add_executable({{appname}} {% for s in appsources %} {{s}} {% endfor %})
        {% endif %}

        {% if appsources and libsources %}
        target_link_libraries({{appname}} {{libname}})
        {% endif %}
        """)

    t = Template(cmake, trim_blocks=True, lstrip_blocks=True)
    return t.render({"verify": verify,
                     "language": language,
                     "project": project,
                     "libname": libname,
                     "libsources": libsources,
                     "appname": appname,
                     "appsources": appsources,
                     "cmake_version": cmake_version
                     })
