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
        conan_setup()

        {% if variables %}
        defines { {{variables}} }
        {% endif %}
    """
    )

    def __init__(self, conanfile, workspace="*"):
        # '*' is the global workspace
        self._conanfile = conanfile
        self.workspace = workspace
        # TODO: not possible to overwrite upstream defines yet
        self.defines = {}

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
        for key, value in self.defines.items():
            if isinstance(value, bool):
                value = 1 if value else 0
            formated_variables += f'"{key}={value}", '

        content = Template(
            self._premake_file_template, trim_blocks=True, lstrip_blocks=True
        ).render(
            workspace=self.workspace,
            build_folder=Path(self._conanfile.build_folder).as_posix(),
            cppstd=cppstd,
            cstd=cstd,
            variables=formated_variables,
            cross_build_arch=cross_build_arch
        )
        save(
            self,
            os.path.join(self._conanfile.generators_folder, self.filename),
            content,
        )
        # TODO: improve condition
        if "msvc" in self._conanfile.settings.compiler:
            VCVars(self._conanfile).generate()
