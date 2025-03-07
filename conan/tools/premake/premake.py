import textwrap
from pathlib import Path

from jinja2 import Template

from conan.tools.files import save
from conan.tools.microsoft.msbuild import MSBuild
from conan.tools.premake.toolchain import PremakeToolchain

# Source: https://learn.microsoft.com/en-us/cpp/overview/compiler-versions?view=msvc-170
PREMAKE_VS_VERSION = {
    "190": "2015",
    "191": "2017",
    "192": "2019",
    "193": "2022",
    "194": "2022",  # still 2022
}


class Premake:
    """
    Premake cli wrapper
    """

    filename = "conanfile.premake5.lua"

    # Conan premake file which will preconfigure toolchain and then will call the user's premake file
    _premake_file_template = textwrap.dedent(
        """\
    #!lua
    include("{{luafile}}")
    {% if has_conan_toolchain %}
    include("conantoolchain.premake5.lua")
    {% endif %}
    """
    )

    def __init__(self, conanfile):
        self._conanfile = conanfile
        # Path to the root (premake5) lua file
        self.luafile = Path(self._conanfile.source_folder) / "premake5.lua"
        # (key value pairs. Will translate to "--{key}={value}")
        self.arguments = {}  # https://premake.github.io/docs/Command-Line-Arguments/
        self.arguments["scripts"] = self._conanfile.generators_folder
        if self._conanfile.settings.get_safe("arch"):
            self.arguments["arch"] = self._conanfile.settings.arch

        if "msvc" in self._conanfile.settings.compiler:
            msvc_version = PREMAKE_VS_VERSION.get(
                str(self._conanfile.settings.compiler.version)
            )
            self.action = f"vs{msvc_version}"
        else:
            self.action = "gmake"

    @staticmethod
    def _expand_args(args):
        return " ".join([f"--{key}={value}" for key, value in args.items()])

    def configure(self):
        has_conan_toolchain = (
            Path(self._conanfile.generators_folder) / PremakeToolchain.filename
        ).exists()
        content = Template(self._premake_file_template).render(
            has_conan_toolchain=has_conan_toolchain, luafile=self.luafile
        )

        conan_luafile = Path(self._conanfile.build_folder) / self.filename
        save(self._conanfile, conan_luafile, content)

        premake_options = dict()
        premake_options["file"] = conan_luafile

        premake_command = (
            f"premake5 {self._expand_args(premake_options)} {self.action} "
            f"{self._expand_args(self.arguments)}"
        )
        self._conanfile.run(premake_command)


    def build(self, workspace):
        if self.action.startswith("vs"):
            msbuild = MSBuild(self)
            # TODO: init VCVars
            # TODO determine the generated solution name from premake build script
            msbuild.build(sln=f"{workspace}.sln")
        else:
            build_type = str(self._conanfile.settings.build_type)
            self._conanfile.run(f"make config={build_type.lower()} -j")
