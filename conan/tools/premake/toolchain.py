import os
import textwrap

from conan.tools.build.cross_building import cross_building
from conan.tools.build.flags import cppstd_msvc_flag
from conan.tools.microsoft.visual import VCVars
from jinja2 import Environment
from pathlib import Path

from conan.tools.files import save
from conan.tools.premake.premakedeps import PREMAKE_ROOT_FILE

jinja_env = Environment(trim_blocks=True, lstrip_blocks=True)

INDENT_LEVEL = 4
INDENT_SPACES = " " * INDENT_LEVEL

def _generate_flags(self):
    template = jinja_env.from_string(textwrap.dedent(
        """\
        {% if extra_cflags %}
        filter {"files:**.c"}
            buildoptions { {{ extra_cflags }} }
        filter {}
        {% endif %}
        {% if extra_cxxflags %}
        filter {"files:**.cpp", "**.cxx", "**.cc"}
            buildoptions { {{ extra_cxxflags }} }
        filter {}
        {% endif %}
        {% if extra_ldflags %}
        linkoptions { {{ extra_ldflags }} }
        {% endif %}
        {% if variables %}
        defines { {{ variables }} }
        {% endif %}
    """))

    def format_list(items):
        return ", ".join(f'"{item}"' for item in items) if items else None

    formatted_variables = format_list(
        f"{key}={1 if isinstance(value, bool) and value else (0 if isinstance(value, bool) else value)}"
        for key, value in self.extra_defines.items()
    )
    extra_c_flags = format_list(self.extra_cflags)
    extra_cxx_flags = format_list(self.extra_cxxflags)
    extra_ld_flags = format_list(self.extra_ldflags)

    return template.render(
        variables=formatted_variables,
        extra_cflags=extra_c_flags,
        extra_cxxflags=extra_cxx_flags,
        extra_ldflags=extra_ld_flags,
    ).strip()


class _PremakeWorkspace:
    # Main template only handles the workspace definition and includes the body
    _premake_workspace_template = jinja_env.from_string(textwrap.dedent(
        """\
    {% if is_global %}
    for wks in premake.global.eachWorkspace() do
        workspace(wks.name)
    {{ workspace_body | indent(indent_level, first=True) }}
    end -- End of for wks loop
    {% else %}
    workspace "{{ name }}"
    {{ workspace_body | indent(indent_level, first=True) }}
    {% endif %}
    """))

    # Template for the content INSIDE a workspace block
    _workspace_body_template = jinja_env.from_string(textwrap.dedent(
        """\
        location(locationDir)
        targetdir(path.join(locationDir, "bin"))
        objdir(path.join(locationDir, "obj"))

        {% if cppstd %}
        cppdialect "{{ cppstd }}"
        {% endif %}
        {% if cstd %}
        cdialect "{{ cstd }}"
        {% endif %}

        {% if cross_build_arch %}
        -- TODO: this should be fixed by premake: https://github.com/premake/premake-core/issues/2136
        buildoptions "-arch {{ cross_build_arch }}"
        linkoptions "-arch {{ cross_build_arch }}"
        {% endif %}

        {% if flags %}
        -- Workspace flags
    {{ flags | indent(indent_level, first=True) }}
        {% endif %}

        filter { "system:macosx" }
        {{ indent_spaces }}-- runpathdirs { "@loader_path" }
        {{ indent_spaces }}linkoptions { "-Wl,-rpath,@loader_path" }
        filter {}

        conan_setup()

        {% for project in projects.values() %}

    {{ project._generate(current_indent_level + indent_level) | indent(indent_level, first=True) }}
        {% endfor %}
    """))

    def __init__(self, name, conanfile) -> None:
        self.name = name
        self.is_global = name == "*"
        self._projects = {}
        self._conanfile = conanfile
        self.extra_cxxflags = []
        self.extra_cflags = []
        self.extra_ldflags = []
        self.extra_defines = {}

    def project(self, project_name):
        if project_name not in self._projects:
            workspace_context_name = "wks" if self.is_global else f'"{self.name}"'
            self._projects[project_name] = _PremakeProject(project_name, workspace_context_name)
        return self._projects[project_name]

    def _generate_body(self, current_indent_level):
        """Generates the inner content of the workspace block."""
        cppstd = self._conanfile.settings.get_safe("compiler.cppstd")
        if cppstd:
            if cppstd.startswith("gnu"):
                cppstd = f"gnu++{cppstd[3:]}"
            elif self._conanfile.settings.os == "Windows":
                cppstd = cppstd_msvc_flag(str(self._conanfile.settings.compiler.version), cppstd)
        cstd = self._conanfile.settings.get_safe("compiler.cstd")
        cross_build_arch = self._conanfile.settings.arch if cross_building(self._conanfile) else None

        flags_content = _generate_flags(self) # Generate flags specific to this workspace

        return self._workspace_body_template.render(
            cppstd=cppstd,
            cstd=cstd,
            cross_build_arch=cross_build_arch,
            projects=self._projects,
            flags=flags_content,
            indent_level=INDENT_LEVEL,
            indent_spaces=INDENT_SPACES,
            current_indent_level=current_indent_level
        )

    def _generate(self, current_indent_level=0):
        """Generates the full workspace block (header + body)."""
        workspace_body_content = self._generate_body(current_indent_level)

        return self._premake_workspace_template.render(
            is_global=self.is_global,
            name=self.name,
            workspace_body=workspace_body_content,
            indent_level=INDENT_LEVEL
        )


class _PremakeProject:
    # Main template only handles the project definition and includes the body
    _premake_project_template = jinja_env.from_string(textwrap.dedent(
        """\
    {% if is_global %}
    for prj in premake.workspace.eachproject({{ workspace_context_name }}) do
        project(prj.name)
    {{ project_body | indent(indent_level, first=True) }}
    end -- End of for prj loop
    {% else %}
    project "{{ name }}"
    {{ project_body | indent(indent_level, first=True) }}
    {% endif %}
    """))

    # Template for the content INSIDE a project block
    _project_body_template = jinja_env.from_string(textwrap.dedent(
        """\
        {% if kind %}
        kind "{{ kind }}"
        {% endif %}
        {% if flags %}
        -- Project flags {{ "(global)" if is_global else "(specific)"}}
    {{ flags | indent(indent_level, first=True) }}
        {% endif %}
        -- Add other project settings here
    """))

    def __init__(self, name, workspace_context_name) -> None:
        self.name = name
        self.workspace_context_name = workspace_context_name
        self.is_global = self.name == "*"
        self.kind = None
        self.extra_cxxflags = []
        self.extra_cflags = []
        self.extra_ldflags = []
        self.extra_defines = {}

    def _generate_body(self, current_indent_level):
        """Generates the inner content of the project block."""
        flags_content = _generate_flags(self) # Generate flags specific to this project

        return self._project_body_template.render(
            kind=self.kind,
            flags=flags_content,
            is_global=self.is_global, # Pass is_global for the comment
            indent_level=INDENT_LEVEL,
            indent_spaces=INDENT_SPACES,
            current_indent_level=current_indent_level
        )

    def _generate(self, current_indent_level=0):
        """Generates the full project block (header + body)."""
        project_body_content = self._generate_body(current_indent_level)

        return self._premake_project_template.render(
            is_global=self.is_global,
            name=self.name,
            workspace_context_name=self.workspace_context_name,
            project_body=project_body_content,
            indent_level=INDENT_LEVEL
        )


class PremakeToolchain:
    """
    PremakeToolchain generator
    """

    filename = "conantoolchain.premake5.lua"
    # Keep template indented correctly for Lua output
    _premake_file_template = textwrap.dedent(
        """\
    #!lua
    -- Conan auto-generated toolchain file
    {% if has_conan_deps %}
    -- Include conandeps.premake5.lua with Conan dependency setup
    include("conandeps.premake5.lua")
    {% endif %}

    -- Base build directory
    local locationDir = path.normalize("{{ build_folder }}")

    -- Generate workspace configurations
    {% for workspace in workspaces.values() %}
    {{ workspace._generate() }}
    {% endfor %}
    """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._workspaces = {}
        # Toolchain-level flags (will be pushed to global workspace)
        self.extra_cxxflags = []
        self.extra_cflags = []
        self.extra_ldflags = []
        self.extra_defines = {}

    def workspace(self, workspace_name):
        if workspace_name not in self._workspaces:
            self._workspaces[workspace_name] = _PremakeWorkspace(workspace_name, self._conanfile)
        return self._workspaces[workspace_name]

    def project(self, project_name, workspace_name = '*'):
        if workspace_name not in self._workspaces:
            self.workspace(workspace_name)
        return self._workspaces[workspace_name].project(project_name)

    def generate(self):
        # Assign toolchain-level flags to the global workspace ('*')
        global_ws = self.workspace("*")
        # Combine potentially pre-set flags with toolchain level ones
        global_ws.extra_cxxflags = list(set(global_ws.extra_cxxflags + self.extra_cxxflags))
        global_ws.extra_cflags = list(set(global_ws.extra_cflags + self.extra_cflags))
        global_ws.extra_ldflags = list(set(global_ws.extra_ldflags + self.extra_ldflags))
        global_ws.extra_defines.update(self.extra_defines) # Merge defines

        premake_conan_deps = Path(self._conanfile.generators_folder) / PREMAKE_ROOT_FILE
        template = jinja_env.from_string(self._premake_file_template)
        content = template.render(
            # Pass posix path for better cross-platform compatibility in Lua
            build_folder=Path(self._conanfile.build_folder).as_posix(),
            has_conan_deps=premake_conan_deps.exists(),
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
