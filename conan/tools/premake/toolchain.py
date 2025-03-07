import os
import textwrap

from jinja2 import Template

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


    workspace "{{workspace}}"
        premake.api.addAliases("architecture", {
          ["armv8"] = "arm64"
        })

        {% if cppstd %}
        cppdialect "{{cppstd}}"
        {% endif %}
        {% if cstd %}
        cdialect "{{cstd}}"
        {% endif %}
        location "{{ build_folder }}"
        targetdir "{{ build_folder }}"
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
        cstd = self._conanfile.settings.get_safe("compiler.cstd")
        if cppstd.startswith("gnu"):
            cppstd = f"gnu++{cppstd[3:]}"

        formated_variables = ""
        for key, value in self.defines.items():
            if isinstance(value, bool):
                value = 1 if value else 0
            formated_variables += f'"{key}={value}", '

        content = Template(
            self._premake_file_template, trim_blocks=True, lstrip_blocks=True
        ).render(
            workspace=self.workspace,
            build_folder=self._conanfile.build_folder,
            cppstd=cppstd,
            cstd=cstd,
            variables=formated_variables,
        )
        save(
            self,
            os.path.join(self._conanfile.generators_folder, self.filename),
            content,
        )
