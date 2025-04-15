import os
import textwrap

from conan.tools.build.cross_building import cross_building
from conan.tools.build.flags import cppstd_msvc_flag
from conan.tools.microsoft.visual import VCVars
from jinja2 import Environment
from pathlib import Path

from conan.tools.files import save
from conan.tools.premake.premakedeps import PREMAKE_ROOT_FILE
from conan.tools.premake.constants import INDENT_LEVEL

_jinja_env = Environment(trim_blocks=True, lstrip_blocks=True)

def _generate_flags(self):
    template = _jinja_env.from_string(textwrap.dedent(
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


class _PremakeProject:
    _premake_project_template = _jinja_env.from_string(textwrap.dedent(
        """\
    project "{{ name }}"
        {% if kind %}
        kind "{{ kind }}"
        {% endif %}
        {% if flags %}
        -- Project flags {{ "(global)" if is_global else "(specific)"}}
    {{ flags | indent(indent_level, first=True) }}
        {% endif %}
    """))

    def __init__(self, name) -> None:
        self.name = name
        self.kind = None
        self.extra_cxxflags = []
        self.extra_cflags = []
        self.extra_ldflags = []
        self.extra_defines = {}
        self.disable = False

    def _generate(self):
        """Generates project block"""
        flags_content = _generate_flags(self) # Generate flags specific to this project
        return self._premake_project_template.render(
            name=self.name,
            kind="None" if self.disable else self.kind,
            flags=flags_content,
            indent_level=INDENT_LEVEL,
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
    workspace "{{ workspace }}"
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
            -- runpathdirs { "@loader_path" }
            linkoptions { "-Wl,-rpath,@loader_path" }
        filter {}

        conan_setup()

        {% for project in projects.values() %}

    {{ project._generate() }}
        {% endfor %}
    """)


    def __init__(self, conanfile, workspace: str):
        self._conanfile = conanfile
        self._workspace_name = workspace
        self._projects = {}
        self.extra_cxxflags = []
        self.extra_cflags = []
        self.extra_ldflags = []
        self.extra_defines = {}

    def project(self, project_name):
        if project_name not in self._projects:
            self._projects[project_name] = _PremakeProject(project_name)
        return self._projects[project_name]

    def generate(self):
        premake_conan_deps = Path(self._conanfile.generators_folder) / PREMAKE_ROOT_FILE
        cppstd = self._conanfile.settings.get_safe("compiler.cppstd")
        if cppstd:
            if cppstd.startswith("gnu"):
                cppstd = f"gnu++{cppstd[3:]}"
            elif self._conanfile.settings.os == "Windows":
                cppstd = cppstd_msvc_flag(str(self._conanfile.settings.compiler.version), cppstd)
        cstd = self._conanfile.settings.get_safe("compiler.cstd")
        cross_build_arch = self._conanfile.settings.arch if cross_building(self._conanfile) else None

        flags_content = _generate_flags(self) # Generate flags specific to this workspace

        template = _jinja_env.from_string(self._premake_file_template)
        content = template.render(
            # Pass posix path for better cross-platform compatibility in Lua
            build_folder=Path(self._conanfile.build_folder).as_posix(),
            has_conan_deps=premake_conan_deps.exists(),
            workspace=self._workspace_name,
            cppstd=cppstd,
            cstd=cstd,
            cross_build_arch=cross_build_arch,
            projects=self._projects,
            flags=flags_content,
            indent_level=INDENT_LEVEL,
        )
        save(
            self,
            os.path.join(self._conanfile.generators_folder, self.filename),
            content,
        )
        # TODO: improve condition
        if "msvc" in self._conanfile.settings.compiler:
            VCVars(self._conanfile).generate()
