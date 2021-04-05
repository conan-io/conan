import textwrap

from jinja2 import Template

_makefile_am = """
{% if main %}
bin_PROGRAMS = {{ main }}
{{main}}_SOURCES = {{ main_srcs }}
{% endif %}
{% if lib %}
lib_LIBRARIES = {{ lib }}
{{lib.replace(".", "_")}}_SOURCES = {{ lib_srcs }}
{% endif %}
{% if main and lib %}
{{main}}_LDADD = {{ lib }}
{% endif %}
"""


def gen_makefile_am(**context):
    t = Template(_makefile_am)
    return t.render(**context)


_configure_ac = """
AC_INIT([main], [1.0], [some@email.com])
AM_INIT_AUTOMAKE([-Wall -Werror foreign])
AC_PROG_CXX
AC_PROG_RANLIB
AM_PROG_AR
AC_CONFIG_FILES([Makefile])
AC_OUTPUT
"""


def gen_configure_ac(**context):
    t = Template(_configure_ac)
    return t.render(**context)


def gen_makefile(**context):
    makefile = textwrap.dedent("""\
        .PHONY: all
        all: apps libs

        apps: {% for s in apps %} {{s}} {% endfor %}

        libs: {% for s in libs %} lib{{s}}.a {% endfor %}

        {%- set link_libs = namespace(str='') %}
        {% for lib in libs %}
        {%- set link_libs.str = link_libs.str + ' -l' + lib|string  %}
        lib{{lib}}.a: {{lib}}.o
        	$(AR) rcs lib{{lib}}.a {{lib}}.o
        {% endfor %}

        {% for s in apps %}
        {{s}}: {{s}}.o libs
        	$(CXX) $(CXXFLAGS) $(CPPFLAGS) $(LDFLAGS) -o {{s}} {{s}}.o $(LIBS) {{link_libs.str}} -L.
        {% endfor %}
        """)

    t = Template(makefile)
    return t.render(**context)
