# coding=utf-8

import platform
import textwrap

from jinja2 import Template

from conans.client.build.compiler_flags import build_type_define, architecture_flag, \
    build_type_flags, libcxx_define, libcxx_flag
from conans.client.build.cppstd_flags import cppstd_flag_new as cppstd_flag
from conans.client.tools.oss import cross_building, \
    detected_architecture, detected_os, get_gnu_triplet, get_target_os_arch, get_build_os_arch
from conans.errors import ConanException
from conans.util.files import save


class MakeToolchain(object):
    filename = "conan_toolchain.mak"

    _template_toolchain = textwrap.dedent("""
        # Conan generated toolchain file
        ifndef CONAN_TOOLCHAIN_INCLUDED
            CONAN_TOOLCHAIN_INCLUDED = TRUE

            # Automatic Conan Toolchain Variables
        {%- if build_type %}
            CONAN_TC_BUILD_TYPE = {{build_type}}
        {%- endif -%}
        {%- if os_host %}
            CONAN_TC_OS_HOST = {{os_host}}
        {%- endif %}
        {%- if arch_host %}
            CONAN_TC_ARCH_HOST = {{arch_host}}
        {%- endif %}
        {%- if triplet_host %}
            CONAN_TC_TRIPLET_HOST = {{triplet_host}}
        {%- endif %}
        {%- if os_build %}
            CONAN_TC_OS_BUILD = {{os_build}}
        {%- endif %}
        {%- if arch_build %}
            CONAN_TC_ARCH_BUILD = {{arch_build}}
        {%- endif %}
        {%- if triplet_build %}
            CONAN_TC_TRIPLET_BUILD = {{triplet_build}}
        {%- endif %}
        {%- if os_target %}
            CONAN_TC_OS_TARGET = {{os_target}}
        {%- endif %}
        {%- if arch_target %}
            CONAN_TC_ARCH_TARGET = {{arch_target}}
        {%- endif %}
        {%- if triplet_target %}
            CONAN_TC_TRIPLET_TARGET = {{triplet_target}}
        {%- endif %}
        {%- if compiler %}
            CONAN_TC_COMPILER = {{compiler}}
        {%- endif %}
        {%- if compiler_version %}
            CONAN_TC_COMPILER_VERSION = {{compiler_version}}
        {%- endif %}
        {%- if compiler_runtime %}
            CONAN_TC_COMPILER_RUNTIME = {{compiler_runtime}}
        {%- endif %}

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

            # C++ Standard Library compiler flag
        {%- if libcxx_flag %}
            CONAN_TC_CXXFLAGS += {{ libcxx_flag }}
        {%- endif %}

            # C++ Standard compiler flag
        {%- if cppstd_flag %}
            CONAN_TC_CXXFLAGS += {{cppstd_flag}}
        {%- endif %}

            # Build Type compiler flag
        {%- if build_type_flags -%}
        {% set build_type_flags_joined = build_type_flags|join(" ") %}
            CONAN_TC_CFLAGS += {{ build_type_flags_joined }}
            CONAN_TC_CXXFLAGS += {{ build_type_flags_joined }}
        {%- endif %}

            # Architecture compiler flag
        {%- if arch_flag %}
            CONAN_TC_CFLAGS += {{arch_flag}}
            CONAN_TC_CXXFLAGS += {{arch_flag}}
        {%- endif %}

            # Position-independent code
        {%- if fpic -%}
        {% set fpic_flag = "-fPIC" %}
            CONAN_TC_CFLAGS += {{fpic_flag}}
            CONAN_TC_CXXFLAGS += {{fpic_flag}}
            CONAN_TC_SHARED_LINKER_FLAGS += {{fpic_flag}}
        {%- endif %}

        endif

        # Call this function in your Makefile to have Conan variables added to the standard variables
        # Example:  $(call CONAN_TC_SETUP)

        CONAN_TC_SETUP = $(eval CFLAGS += $(CONAN_TC_CFLAGS)) ; \\
                         $(eval CXXFLAGS += $(CONAN_TC_CXXFLAGS)) ; \\
                         $(eval CPPFLAGS += $(CONAN_TC_CPPFLAGS)) ; \\
                         $(eval LDFLAGS += $(CONAN_TC_LDFLAGS)) ;

    """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._build_type = conanfile.settings.get_safe("build_type")
        self._compiler = conanfile.settings.get_safe("compiler")
        self._compiler_version = conanfile.settings.get_safe("compiler.version")
        self._compiler_runtime = conanfile.settings.get_safe("compiler.runtime")
        self._shared = self._conanfile.options.get_safe("shared")
        self._fpic = self._deduce_fpic()

        self._libcxx_flag = libcxx_flag(conanfile.settings)
        self._cppstd_flag = cppstd_flag(conanfile.settings)
        self._skip_rpath = True if self._conanfile.settings.get_safe("os") == "Macos" else False
        self._arch_flag = architecture_flag(self._conanfile.settings)
        self._build_type_flags = build_type_flags(self._conanfile.settings)

        self._os_host = conanfile.settings.get_safe("os")
        self._arch_host = conanfile.settings.get_safe("arch")
        self._os_target, self._arch_target = get_target_os_arch(conanfile)
        self._arch_build, self._os_build = self._get_build_os_arch()

        self._trip_build, self._trip_host, self._trip_target = self._get_host_build_target_flags()

        self._build_type_define = build_type_define(build_type=self._build_type)
        self._glibcxx_define = libcxx_define(self._conanfile.settings)

        self.variables = {}
        self.preprocessor_definitions = {}

    def _get_host_build_target_flags(self):
        """Based on google search for build/host triplets, it could need a lot
        and complex verification"""

        if self._os_target and self._arch_target:
            try:
                target = get_gnu_triplet(self._os_target, self._arch_target, self._compiler)
            except ConanException as exc:
                self._conanfile.output.warn(str(exc))
                target = None
        else:
            target = None

        if self._os_build is None \
            or self._arch_build is None \
            or self._arch_host is None \
                or self._os_host is None:
            return False, False, target

        if not cross_building(self._conanfile, self._os_build, self._arch_build):
            return False, False, target

        try:
            build = get_gnu_triplet(self._os_build, self._arch_build, self._compiler)
        except ConanException as exc:
            self._conanfile.output.warn(str(exc))
            build = None
        try:
            host = get_gnu_triplet(self._os_host, self._arch_host, self._compiler)
        except ConanException as exc:
            self._conanfile.output.warn(str(exc))
            host = None
        return build, host, target

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
            "build_type": self._build_type,
            "os_host": self._os_host,
            "arch_host": self._arch_host,
            "triplet_host": self._trip_host,
            "os_build": self._os_build,
            "arch_build": self._arch_build,
            "triplet_build": self._trip_build,
            "os_target": self._os_target,
            "arch_target": self._arch_target,
            "triplet_target": self._trip_target,
            "compiler": self._compiler,
            "compiler_version": self._compiler_version,
            "compiler_runtime": self._compiler_runtime,
            "libcxx_flag": self._libcxx_flag,
            "cppstd_flag": self._cppstd_flag,
            "arch_flag": self._arch_flag,
            "build_type_flags": self._build_type_flags,
            "fpic": self._fpic,
            "shared": self._shared,
        }
        t = Template(self._template_toolchain)
        content = t.render(**context)
        return content

    def _deduce_fpic(self):
        fpic = self._conanfile.options.get_safe("fPIC")
        if fpic is None:
            return None
        os_ = self._conanfile.settings.get_safe("os")
        if os_ and "Windows" in os_:
            self._conanfile.output.warn("Toolchain: Ignoring fPIC option defined for Windows")
            return None
        return fpic
