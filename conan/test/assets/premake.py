import textwrap

from jinja2 import Template


def gen_premake5(workspace, projects, includedirs=["."], language="CXX", std="17"):
    premake5 = textwrap.dedent("""\
        workspace "{{workspace}}"
            cppdialect "C++17"
            configurations { "Debug", "Release" }
            fatalwarnings {"All"}
            floatingpoint "Fast"
            includedirs {{premake_quote(includedirs)}}
            filter "configurations:Debug"
               defines { "DEBUG" }
               symbols "On"

            filter "configurations:Release"
               defines { "NDEBUG" }
               optimize "On"

        {% for project in projects %}
        project "{{project["name"]}}"
            kind "{{project["kind"] or 'StaticLib'}}"
            language "{{project["language"] or 'C++'}}"
            files {{premake_quote(project["files"])}}
            links {{premake_quote(project["links"])}}
        {% endfor %}
        """)

    t = Template(premake5, trim_blocks=True, lstrip_blocks=True)

    def premake_quote(s):
        return '{' + ', '.join(['"{}"'.format(s) for s in s]) + '}'

    return t.render(
        {
            "premake_quote": premake_quote,
            "workspace": workspace,
            "includedirs": includedirs,
            "projects": projects,
        }
    )

