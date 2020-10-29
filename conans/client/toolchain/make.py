# coding=utf-8

import platform
import textwrap
from collections import OrderedDict

from jinja2 import Template
from conans.client.build.compiler_flags import build_type_define, libcxx_define
from conans.client.tools.oss import detected_architecture, detected_os, get_build_os_arch
from conans.util.files import save


class MakeToolchain(object):
    filename = "conan_toolchain.mak"

    _template_toolchain = textwrap.dedent("""
        # Conan generated toolchain file
        ifndef CONAN_TOOLCHAIN_INCLUDED
            CONAN_TOOLCHAIN_INCLUDED = TRUE

            # Recipe-Defined Variables
        {%- for it, value in variables.items() %}
            {{ it }} = {{ value }}
        {%- endfor %}

            # Automatic Conan pre-processor definition: build_type_define
        {%- if build_type_define %}
            CONAN_TC_CPPFLAGS += -D{{build_type_define}}
        {%- endif %}

            # Automatic Conan pre-processor definition: glibcxx_define
        {%- if glibcxx_define %}
            CONAN_TC_CPPFLAGS += -D{{glibcxx_define}}
        {%- endif %}

            # Recipe-Defined pre-processor definitions
        {%- if preprocessor_definitions %}
            CONAN_TC_CPPFLAGS = -D{{ preprocessor_definitions|join(" -D")}}
        {%- endif %}

        endif

    """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._build_type = conanfile.settings.get_safe("build_type")

        self._build_type_define = build_type_define(build_type=self._build_type)
        self._glibcxx_define = libcxx_define(self._conanfile.settings)

        self.variables = OrderedDict()
        self.preprocessor_definitions = OrderedDict()

    def _get_build_os_arch(self):
        if hasattr(self._conanfile, 'settings_build'):
            os_build, arch_build = get_build_os_arch(self._conanfile)
        else:
            # FIXME: Why not use 'os_build' and 'arch_build' from conanfile.settings?
            os_build = detected_os() or platform.system()
            arch_build = detected_architecture() or platform.machine()
        return arch_build, os_build

    def write_toolchain_files(self):
        save(self.filename, self.content)

    @property
    def content(self):
        context = {
            "variables": self.variables,
            "glibcxx_define": self._glibcxx_define,
            "build_type_define": self._build_type_define,
            "preprocessor_definitions": self.preprocessor_definitions,
        }
        t = Template(self._template_toolchain)
        content = t.render(**context)
        return content
