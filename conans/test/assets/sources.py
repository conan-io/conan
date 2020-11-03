from jinja2 import Template

_function_cpp = r"""
{% if name != "main" %}
#include "{{name}}.h"
{% endif %}

#include <iostream>

{% if includes %}{% for it in includes -%}
#include "{{it}}.h"
{%- endfor %}{% endif %}

int {{name}}(){
    #ifdef NDEBUG
    std::cout << "{{ msg|default(name) }}: Release!\n";
    #else
    std::cout << "{{msg}}: Debug!\n";
    #endif

    #ifdef _M_X64
    std::cout << "  {{msg}} _M_X64 defined\n";
    #endif

    #ifdef _M_IX86
    std::cout << "  {{msg}} _M_IX86 defined\n";
    #endif

    #if _MSC_VER
    std::cout << "  {{msg}} _MSC_VER" << _MSC_VER<< "\n";
    #endif

    #if _MSVC_LANG
    std::cout << "  {{msg}} _MSVC_LANG" << _MSVC_LANG<< "\n";
    #endif

    {% for it in preprocessor -%}
    std::cout << "  {{msg}} {{it}}: " <<  {{it}} << "\n";
    {%- endfor %}

    {% for it in calls -%}
    {{it}}();
    {%- endfor %}
    return 0;
}
"""


def gen_function_cpp(**context):
    t = Template(_function_cpp)
    return t.render(**context)


_function_h = """
#pragma once

{% for it in includes -%}
#include "{{it}}.h"
{%- endfor %}

#ifdef _WIN32
  #define {{name.upper()}}_EXPORT __declspec(dllexport)
#else
  #define {{name.upper()}}_EXPORT
#endif
{{name.upper()}}_EXPORT int {{name}}();
"""


def gen_function_h(name, includes=None):
    t = Template(_function_h)
    return t.render(name=name, includes=includes or [])
