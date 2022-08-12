from jinja2 import Template

_function_cpp = r"""
{% if name != "main" %}
#include "{{name}}.h"
{% endif %}

#include <iostream>

{% for it in includes -%}
#include "{{it}}.h"
{% endfor %}

int {{name}}(){
    #ifdef NDEBUG
    std::cout << "{{ msg or name }}: Release!\n";
    #else
    std::cout << "{{ msg or name }}: Debug!\n";
    #endif

    // ARCHITECTURES
    #ifdef _M_X64
    std::cout << "  {{ msg or name }} _M_X64 defined\n";
    #endif

    #ifdef _M_IX86
    std::cout << "  {{ msg or name }} _M_IX86 defined\n";
    #endif

    #ifdef _M_ARM64
    std::cout << "   {{ msg or name }} _M_ARM64 defined\n";
    #endif

    #if __i386__
    std::cout << "  {{ msg or name }} __i386__ defined\n";
    #endif

    #if __x86_64__
    std::cout << "  {{ msg or name }} __x86_64__ defined\n";
    #endif
  
    #if __aarch64__
    std::cout << "  {{ msg or name }} __aarch64__ defined\n";
    #endif

    // Libstdc++
    #if defined _GLIBCXX_USE_CXX11_ABI
    std::cout << "  {{ msg or name }} _GLIBCXX_USE_CXX11_ABI "<< _GLIBCXX_USE_CXX11_ABI << "\n";
    #endif

    // COMPILER VERSIONS
    #if _MSC_VER
    std::cout << "  {{ msg or name }} _MSC_VER" << _MSC_VER<< "\n";
    #endif

    #if _MSVC_LANG
    std::cout << "  {{ msg or name }} _MSVC_LANG" << _MSVC_LANG<< "\n";
    #endif

    #if __cplusplus
    std::cout << "  {{ msg or name }} __cplusplus" << __cplusplus<< "\n";
    #endif

    #if __INTEL_COMPILER
    std::cout << "  {{ msg or name }} __INTEL_COMPILER" << __INTEL_COMPILER<< "\n";
    #endif

    #if __GNUC__
    std::cout << "  {{ msg or name }} __GNUC__" << __GNUC__<< "\n";
    #endif

    #if __GNUC_MINOR__
    std::cout << "  {{ msg or name }} __GNUC_MINOR__" << __GNUC_MINOR__<< "\n";
    #endif

    #if __clang_major__
    std::cout << "  {{ msg or name }} __clang_major__" << __clang_major__<< "\n";
    #endif

    #if __clang_minor__
    std::cout << "  {{ msg or name }} __clang_minor__" << __clang_minor__<< "\n";
    #endif

    #if __apple_build_version__
    std::cout << "  {{ msg or name }} __apple_build_version__" << __apple_build_version__<< "\n";
    #endif

    // SUBSYSTEMS

    #if __MSYS__
    std::cout << "  {{ msg or name }} __MSYS__" << __MSYS__<< "\n";
    #endif

    #if __MINGW32__
    std::cout << "  {{ msg or name }} __MINGW32__" << __MINGW32__<< "\n";
    #endif

    #if __MINGW64__
    std::cout << "  {{ msg or name }} __MINGW64__" << __MINGW64__<< "\n";
    #endif

    #if __CYGWIN__
    std::cout << "  {{ msg or name }} __CYGWIN__" << __CYGWIN__<< "\n";
    #endif

    {% for it in preprocessor -%}
    std::cout << "  {{msg}} {{it}}: " <<  {{it}} << "\n";
    {%- endfor %}

    {% for it in calls -%}
    {{it}}();
    {% endfor %}
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


def gen_function_h(**context):
    t = Template(_function_h)
    return t.render(**context)
