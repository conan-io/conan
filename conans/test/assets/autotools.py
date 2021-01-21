from jinja2 import Template

_makefile_am = '''
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
'''


def gen_makefile_am(**context):
    t = Template(_makefile_am)
    return t.render(**context)


_configure_ac = '''
AC_INIT([main], [1.0], [some@email.com])
AM_INIT_AUTOMAKE([-Wall -Werror foreign])
AC_PROG_CXX
AC_PROG_RANLIB
AM_PROG_AR
AC_CONFIG_FILES([Makefile])
AC_OUTPUT
'''


def gen_configure_ac(**context):
    t = Template(_configure_ac)
    return t.render(**context)
