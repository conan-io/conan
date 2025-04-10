import os
import textwrap

from conan.tools.build.cross_building import cross_building
from conan.tools.build.flags import cppstd_msvc_flag
from conan.tools.microsoft.visual import VCVars
from jinja2 import Template
from pathlib import Path

from conan.tools.files import save


class PremakeToolchain:
    """
    PremakeToolchain generator
    """

    filename = "conantoolchain.premake5.lua"

    _premake_file_template = textwrap.dedent(
        """\
    #!lua
    include("conandeps.premake5.lua")

    local locationDir = "{{ build_folder }}"

    workspace "{{workspace}}"
        {% if cppstd %}
        cppdialect "{{cppstd}}"
        {% endif %}
        {% if cstd %}
        cdialect "{{cstd}}"
        {% endif %}
        location(locationDir)
        targetdir(path.join(locationDir, "bin"))
        objdir(path.join(locationDir, "obj"))

        {% if cross_build_arch %}
        -- TODO: this should be fixed by premake: https://github.com/premake/premake-core/issues/2136
        buildoptions "-arch {{cross_build_arch}}"
        linkoptions "-arch {{cross_build_arch}}"
        {% endif %}

        {% if extra_cflags %}
        filter { "language:C" }
            buildoptions { {{extra_cflags}} }
        filter {}
        {% endif %}
        {% if extra_cxxflags %}
        filter { "language:C++" }
            buildoptions { {{extra_cxxflags}} }
        filter {}
        {% endif %}
        {% if extra_ldflags %}
        linkoptions { {{extra_ldflags}} }
        {% endif %}

        {% if variables %}
        defines { {{variables}} }
        {% endif %}

        conan_setup()
    """
    )

    def __init__(self, conanfile, workspace="*"):
        # '*' is the global workspace
        self._conanfile = conanfile
        self.workspace = workspace
        # Extra flags
        #: List of extra ``CXX`` flags. Added to ``cpp_args``
        self.extra_cxxflags = []
        #: List of extra ``C`` flags. Added to ``c_args``
        self.extra_cflags = []
        #: List of extra linker flags. Added to ``c_link_args`` and ``cpp_link_args``
        self.extra_ldflags = []
        # TODO: not possible to overwrite upstream defines yet
        self.extra_defines = {}

    def generate(self):
        cppstd = self._conanfile.settings.get_safe("compiler.cppstd")
        if cppstd:
            # TODO
            if cppstd.startswith("gnu"):
                cppstd = f"gnu++{cppstd[3:]}"
            elif self._conanfile.settings.os == "Windows":
                cppstd = cppstd_msvc_flag(str(self._conanfile.settings.compiler.version), cppstd)
        cstd = self._conanfile.settings.get_safe("compiler.cstd")
        cross_build_arch = self._conanfile.settings.arch if cross_building(self._conanfile) else None

        formated_variables = ""
        for key, value in self.extra_defines.items():
            if isinstance(value, bool):
                value = 1 if value else 0
            formated_variables += f'"{key}={value}", '

        extra_c_flags = ",".join(f'"{flag}"' for flag in self.extra_cflags) if self.extra_cflags else None
        extra_cxx_flags = ",".join(f'"{flag}"' for flag in self.extra_cxxflags) if self.extra_cxxflags else None
        extra_ld_flags = ",".join(f'"{flag}"' for flag in self.extra_ldflags) if self.extra_ldflags else None

        content = Template(
            self._premake_file_template, trim_blocks=True, lstrip_blocks=True
        ).render(
            workspace=self.workspace,
            build_folder=Path(self._conanfile.build_folder).as_posix(),
            cppstd=cppstd,
            cstd=cstd,
            variables=formated_variables,
            cross_build_arch=cross_build_arch,
            extra_cflags=extra_c_flags,
            extra_cxxflags=extra_cxx_flags,
            extra_ldflags=extra_ld_flags,
        )
        save(
            self,
            os.path.join(self._conanfile.generators_folder, self.filename),
            content,
        )
        # TODO: improve condition
        if "msvc" in self._conanfile.settings.compiler:
            VCVars(self._conanfile).generate()
