import os
import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient
from conan.test.assets.sources import gen_function_cpp

@pytest.mark.skipif(platform.system() != "Linux", reason="Premake only installed on Linux CI machines")
@pytest.mark.skipif(platform.machine() != "x86_64", reason="Premake Legacy generator only supports x86_64 machines")
@pytest.mark.tool("premake")
def test_premake_legacy(matrix_client):
    c = matrix_client
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.premake import Premake
        from conan.tools.microsoft import MSBuild
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            requires = "matrix/1.0"
            generators = "PremakeDeps", "VCVars"
            def build(self):
                p = Premake(self)
                p.configure()
                build_type = str(self.settings.build_type)
                if self.settings.os == "Windows":
                    msbuild = MSBuild(self)
                    msbuild.build("HelloWorld.sln")
                else:
                    self.run(f"make config={build_type.lower()}_x86_64")
                p = os.path.join(self.build_folder, "bin", build_type, "HelloWorld")
                self.run(f'"{p}"')
        """)
    premake = textwrap.dedent("""
        -- premake5.lua

        include('conandeps.premake5.lua')

        workspace "HelloWorld"
           conan_setup()
           configurations { "Debug", "Release" }
           platforms { "x86_64" }

        project "HelloWorld"
           kind "ConsoleApp"
           language "C++"
           targetdir "bin/%{cfg.buildcfg}"

           files { "**.h", "**.cpp" }

           filter "configurations:Debug"
              defines { "DEBUG" }
              symbols "On"

           filter "configurations:Release"
              defines { "NDEBUG" }
              optimize "On"

           filter "platforms:x86_64"
              architecture "x86_64"
          """)
    c.save({"conanfile.py": conanfile,
            "premake5.lua": premake,
            "main.cpp": gen_function_cpp(name="main", includes=["matrix"], calls=["matrix"])})
    c.run("build .")
    assert "main: Release!" in c.out
    assert "matrix/1.0: Hello World Release!" in c.out
    if platform.system() == "Windows":
        assert "main _M_X64 defined" in c.out
    else:
        assert "main __x86_64__ defined" in c.out
    c.run("build . -s build_type=Debug --build=missing")
    assert "main: Debug!" in c.out
    assert "matrix/1.0: Hello World Debug!" in c.out



@pytest.mark.skipif(platform.system() != "Linux", reason="Only for Linux now")
@pytest.mark.tool("premake")
def test_premake_new_generator(matrix_client):
    c = matrix_client

    premake5 = textwrap.dedent(
        """
        workspace "Project"
           language "C++"
           configurations { "Debug", "Release" }

        project "app"
           kind "ConsoleApp"
           files { "**.h", "**.cpp" }
           filter "configurations:Debug"
              defines { "DEBUG" }
              symbols "On"
           filter "configurations:Release"
              defines { "NDEBUG" }
              optimize "On"
    """
    )

    conanfile = textwrap.dedent(
        """
        from conan import ConanFile
        from conan.tools.layout import basic_layout
        from conan.tools.premake import Premake, PremakeDeps, PremakeToolchain
        import os

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            name = "pkg"
            version = "1.0"
            requires = "matrix/1.0"
            generators = "PremakeDeps", "PremakeToolchain"

            def layout(self):
                basic_layout(self, src_folder="src")

            def build(self):
                premake = Premake(self)
                premake.configure()
                premake.build(workspace="Project", targets=["app"])

                # Run executable after build
                p = os.path.join(self.build_folder, "bin", "app")
                self.run(f'"{p}"')
        """
    )

    c.save({"conanfile.py": conanfile,
            "src/premake5.lua": premake5,
            "src/main.cpp": gen_function_cpp(name="main", includes=["matrix"], calls=["matrix"])})

    c.run("build .")
    assert "matrix/1.0: Hello World Release!" in c.out

    c.run("build . -s build_type=Debug --build=missing")
    assert "matrix/1.0: Hello World Debug!" in c.out
