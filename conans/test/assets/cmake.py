import textwrap

from jinja2 import Template


def gen_cmakelists(language="CXX", verify=True, project="project", libname="mylibrary",
                   libsources=None, appname="myapp", appsources=None, cmake_version="3.15",
                   install=False, find_package=None, libtype=""):
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

        {% for s in find_package %}
        find_package({{s}})
        {% endfor %}

        {% if libsources %}
        add_library({{libname}} {{libtype}} {% for s in libsources %} {{s}} {% endfor %})
        {% endif %}

        {% if libsources and find_package %}
        target_link_libraries({{libname}} {% for s in find_package %} {{s}}::{{s}} {% endfor %})
        {% endif %}

        {% if appsources %}
        add_executable({{appname}} {% for s in appsources %} {{s}} {% endfor %})
        {% endif %}

        {% if appsources and libsources %}
        target_link_libraries({{appname}} {{libname}})
        {% endif %}

        {% if appsources and not libsources and find_package %}
        target_link_libraries({{appname}} {% for s in find_package %} {{s}}::{{s}} {% endfor %})
        {% endif %}

        {% if install %}
        install(TARGETS {{appname}} {{libname}} DESTINATION ".")
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
                     "cmake_version": cmake_version,
                     "install": install,
                     "find_package": find_package or [],
                     "libtype": libtype
                     })
