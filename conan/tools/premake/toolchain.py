import os
import textwrap

from conan.tools.build.cross_building import cross_building
from conan.tools.build.flags import cppstd_msvc_flag
from conan.tools.microsoft.visual import VCVars
from jinja2 import Template
from pathlib import Path

from conan.tools.files import save

def _generate_flags(self):
    _premake_flags_template = textwrap.dedent(
        """\
        {% if extra_cflags %}
        filter {"files:**.c"}
            buildoptions { {{extra_cflags}} }
        filter {}
        {% endif %}
        {% if extra_cxxflags %}
        filter {"files:**.cpp or **.cxx or *.cc"}
            buildoptions { {{extra_cxxflags}} }
        filter {}
        {% endif %}
        {% if extra_ldflags %}
        linkoptions { {{extra_ldflags}} }
        {% endif %}

        {% if variables %}
        defines { {{variables}} }
        {% endif %}
    """)

    formated_variables = ""
    for key, value in self.extra_defines.items():
        if isinstance(value, bool):
            value = 1 if value else 0
        formated_variables += f'"{key}={value}", '
    extra_c_flags = ",".join(f'"{flag}"' for flag in self.extra_cflags) if self.extra_cflags else None
    extra_cxx_flags = ",".join(f'"{flag}"' for flag in self.extra_cxxflags) if self.extra_cxxflags else None
    extra_ld_flags = ",".join(f'"{flag}"' for flag in self.extra_ldflags) if self.extra_ldflags else None
    return Template(
        _premake_flags_template, trim_blocks=True, lstrip_blocks=False
    ).render(
        variables=formated_variables,
        extra_cflags=extra_c_flags,
        extra_cxxflags=extra_cxx_flags,
        extra_ldflags=extra_ld_flags,
    )


class _PremakeWorkspace:
    _premake_workspace_template = textwrap.dedent(
        """\
    {% if is_global %}
    for wks in premake.global.eachWorkspace() do
        workspace(wks.name)
    {% else %}
    workspace "{{name}}"
    {% endif %}

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

        {% if flags %}
        {{ flags }}
        {% endif %}

        filter { "system:macosx" }
            -- runpathdirs { "@loader_path" }
            linkoptions { "-Wl,-rpath,@loader_path" }
        filter {}

        conan_setup()

    {% for project in projects.values() %}
    {{ project._generate() }}
    {% endfor %}

    {% if is_global %}
    end
    {% endif %}
    """)

    extra_cxxflags = []
    extra_cflags = []
    extra_ldflags = []
    extra_defines = {}

    def __init__(self, name, conanfile) -> None:
        self.name = name
        self.is_global = name == "*"
        self._projects = {}
        self._conanfile = conanfile

    def project(self, project):
        if project not in self._projects:
            self._projects[project] = _PremakeProject(project, "wks" if self.is_global else self.name)
        return self._projects[project]

    def _generate(self):
        cppstd = self._conanfile.settings.get_safe("compiler.cppstd")
        if cppstd:
            # TODO
            if cppstd.startswith("gnu"):
                cppstd = f"gnu++{cppstd[3:]}"
            elif self._conanfile.settings.os == "Windows":
                cppstd = cppstd_msvc_flag(str(self._conanfile.settings.compiler.version), cppstd)
        cstd = self._conanfile.settings.get_safe("compiler.cstd")
        cross_build_arch = self._conanfile.settings.arch if cross_building(self._conanfile) else None

        return Template(
            self._premake_workspace_template, trim_blocks=True, lstrip_blocks=True
        ).render(is_global=self.is_global,
            name=self.name,
            cppstd=cppstd,
            cstd=cstd,
            cross_build_arch=cross_build_arch,
            projects=self._projects,
            flags=_generate_flags(self),
        )


class _PremakeProject:

    _premake_project_template = textwrap.dedent(
        """\
    {% if is_global %}
    for prj in premake.workspace.eachproject({{ workspace }}) do
        project (prj.name)
    {% else %}
    project "{{ name }}"
    {% endif %}
        {% if kind %}
        kind({{kind}})
        {% endif %}
        {% if flags %}
        {{ flags }}
        {% endif %}
    {% if is_global %}
    end
    {% endif %}
    """
    )

    kind = None
    extra_cxxflags = []
    extra_cflags = []
    extra_ldflags = []
    extra_defines = {}

    def __init__(self, name, workspace) -> None:
        self.name = name
        self.workspace = workspace

    def _generate(self):
        is_global = self.name == "*"
        return Template(
            self._premake_project_template, trim_blocks=True, lstrip_blocks=True
        ).render(
            is_global=is_global,
            name=self.name,
            workspace=self.workspace,
            kind=self.kind,
            flags=_generate_flags(self),
        )


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
    {% for workspace in workspaces.values() %}
    {{ workspace._generate() }}
    {% endfor %}
    """
    )

    def __init__(self, conanfile):
        # '*' is the global workspace
        self._conanfile = conanfile
        self._workspaces = {}

        self.extra_cxxflags = []
        self.extra_cflags = []
        self.extra_ldflags = []
        self.extra_defines = {}

    def workspace(self, workspace):
        if workspace not in self._workspaces:
            self._workspaces[workspace] = _PremakeWorkspace(workspace, self._conanfile)
        return self._workspaces[workspace]

    def project(self, project, workspace = '*'):
        if workspace not in self._workspaces:
            self._workspaces[workspace] = _PremakeWorkspace(workspace, self._conanfile)
        return self._workspaces[workspace].project(project)

    def generate(self):
        self.workspace("*").extra_cxxflags = self.extra_cxxflags
        self.workspace("*").extra_cflags = self.extra_cflags
        self.workspace("*").extra_ldflags = self.extra_ldflags
        self.workspace("*").extra_defines = self.extra_defines

        content = Template(
            self._premake_file_template, trim_blocks=True, lstrip_blocks=True
        ).render(
            workspace=self.workspace,
            build_folder=Path(self._conanfile.build_folder).as_posix(),
            workspaces=self._workspaces,
        )
        save(
            self,
            os.path.join(self._conanfile.generators_folder, self.filename),
            content,
        )
        # TODO: improve condition
        if "msvc" in self._conanfile.settings.compiler:
            VCVars(self._conanfile).generate()
