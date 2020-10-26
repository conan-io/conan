# coding=utf-8

import platform
import textwrap

from jinja2 import Template
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

            # Recipe-Defined pre-processor definitions
        {%- if preprocessor_definitions %}
            CONAN_TC_CPPFLAGS = -D{{ preprocessor_definitions|join(" -D")}}
        {%- endif %}

        endif

    """)

    def __init__(self, conanfile):
        self._conanfile = conanfile

        self.variables = {}
        self.preprocessor_definitions = {}

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
            "preprocessor_definitions": self.preprocessor_definitions,
        }
        t = Template(self._template_toolchain)
        content = t.render(**context)
        return content
