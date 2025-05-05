import platform
import textwrap
import os

import pytest

from conan.test.assets.autotools import gen_makefile_am, gen_configure_ac
from conan.test.assets.genconanfile import GenConanfile
from conan.test.assets.sources import gen_function_cpp
from test.conftest import tools_locations
from test.functional.utils import check_exe_run
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
@pytest.mark.tool("msys2")
def test_autotools_bash_complete():
    client = TestClient(path_with_spaces=False)
    profile_win = textwrap.dedent(f"""
        include(default)
        [conf]
        tools.microsoft.bash:subsystem=msys2
        tools.microsoft.bash:path=bash
        """)

    main = gen_function_cpp(name="main")
    # The autotools support for "cl" compiler (VS) is very limited, linking with deps doesn't
    # work but building a simple app do
    makefile_am = gen_makefile_am(main="main", main_srcs="main.cpp")
    configure_ac = gen_configure_ac()

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import Autotools

        class TestConan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "configure.ac", "Makefile.am", "main.cpp"
            generators = "AutotoolsToolchain"
            win_bash = True

            def build(self):
                # These commands will run in bash activating first the vcvars and
                # then inside the bash activating the
                self.run("aclocal")
                self.run("autoconf")
                self.run("automake --add-missing --foreign")
                autotools = Autotools(self)
                autotools.configure()
                autotools.make()
                autotools.install()
        """)

    client.save({"conanfile.py": conanfile,
                 "configure.ac": configure_ac,
                 "Makefile.am": makefile_am,
                 "main.cpp": main,
                 "profile_win": profile_win})
    client.run("build . -pr=profile_win")
    client.run_command("main.exe")
    check_exe_run(client.out, "main", "msvc", None, "Release", "x86_64", None)

    bat_contents = client.load("conanbuild.bat")
    assert "conanvcvars.bat" in bat_contents


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_add_msys2_path_automatically():
    """ Check that commands like ar, autoconf, etc, that are in the /usr/bin folder together
    with the bash.exe, can be automaticallly used when running in windows bash, without user
    extra addition to [buildenv] of that msys64/usr/bin path

    # https://github.com/conan-io/conan/issues/12110
    """
    client = TestClient(path_with_spaces=False)
    bash_path = None
    try:
        bash_path = tools_locations["msys2"]["system"]["path"]["Windows"] + "/bash.exe"
    except KeyError:
        pytest.skip("msys2 path not defined")

    save(client.paths.new_config_path, textwrap.dedent("""
            tools.microsoft.bash:subsystem=msys2
            tools.microsoft.bash:path={}
            """.format(bash_path)))

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"

            win_bash = True

            def build(self):
                self.run("ar -h")
                """)

    client.save({"conanfile.py": conanfile})
    client.run("create .")
    assert "ar.exe" in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_conf_inherited_in_test_package():
    client = TestClient()
    bash_path = None
    try:
        bash_path = tools_locations["msys2"]["system"]["path"]["Windows"] + "/bash.exe"
    except KeyError:
        pytest.skip("msys2 path not defined")

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Recipe(ConanFile):
            name="msys2"
            version="1.0"

            def package_info(self):
                self.conf_info.define("tools.microsoft.bash:subsystem", "msys2")
                self.conf_info.define("tools.microsoft.bash:path", r"{}")
    """.format(bash_path))
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    conanfile = GenConanfile("consumer", "1.0")
    test_package = textwrap.dedent("""
        from conan import ConanFile

        class Recipe(ConanFile):
            name="test"
            version="1.0"
            win_bash = True

            def build_requirements(self):
                self.tool_requires(self.tested_reference_str)
                self.tool_requires("msys2/1.0")

            def build(self):
                self.output.warning(self.conf.get("tools.microsoft.bash:subsystem"))
                self.run("aclocal --version")

            def test(self):
                pass
        """)
    client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_package})
    client.run("create . -s:b os=Windows -s:h os=Windows")
    assert "are needed to run commands in a Windows subsystem" not in client.out
    assert "aclocal (GNU automake)" in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
@pytest.mark.tool("msys2")
def test_msys2_and_msbuild():
    """ Check that msbuild can be executed in msys2 environment

    # https://github.com/conan-io/conan/issues/15627
    """
    client = TestClient(path_with_spaces=False)
    profile_win = textwrap.dedent(f"""
        include(default)
        [conf]
        tools.microsoft.bash:subsystem=msys2
        tools.microsoft.bash:path=bash
        """)

    main = gen_function_cpp(name="main")
    # The autotools support for "cl" compiler (VS) is very limited, linking with deps doesn't
    # work but building a simple app do
    makefile_am = gen_makefile_am(main="main", main_srcs="main.cpp")
    configure_ac = gen_configure_ac()

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import Autotools
        from conan.tools.microsoft import MSBuild

        class TestConan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "configure.ac", "Makefile.am", "main.cpp", "MyProject.vcxproj"
            generators = "AutotoolsToolchain"
            win_bash = True

            def build(self):
                # These commands will run in bash activating first the vcvars and
                # then inside the bash activating the
                self.run("aclocal")
                self.run("autoconf")
                self.run("automake --add-missing --foreign")
                autotools = Autotools(self)
                autotools.configure()
                autotools.make()
                autotools.install()
                msbuild = MSBuild(self)
                msbuild.build("MyProject.vcxproj")
        """)

    # A minimal project is sufficient - here just copy the application file to another directory
    my_vcxproj = """<?xml version="1.0" encoding="utf-8"?>
        <Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
        <ItemGroup Label="ProjectConfigurations">
        <ProjectConfiguration Include="Debug|Win32">
          <Configuration>Debug</Configuration>
          <Platform>Win32</Platform>
        </ProjectConfiguration>
        <ProjectConfiguration Include="Release|Win32">
          <Configuration>Release</Configuration>
          <Platform>Win32</Platform>
        </ProjectConfiguration>
        <ProjectConfiguration Include="Debug|x64">
          <Configuration>Debug</Configuration>
          <Platform>x64</Platform>
        </ProjectConfiguration>
        <ProjectConfiguration Include="Release|x64">
          <Configuration>Release</Configuration>
          <Platform>x64</Platform>
        </ProjectConfiguration>
      </ItemGroup>
      <PropertyGroup Label="Globals">
        <ProjectGuid>{B58316C0-C78A-4E9B-AE8F-5D6368CE3840}</ProjectGuid>
        <Keyword>Win32Proj</Keyword>
      </PropertyGroup>
      <Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />
      <PropertyGroup>
        <ConfigurationType>Application</ConfigurationType>
        <PlatformToolset>v141</PlatformToolset>
      </PropertyGroup>
      <Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" />
      <ImportGroup Label="PropertySheets">
        <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" />
      </ImportGroup>
      <PropertyGroup>
        <OutDir>$(ProjectDir)msbuild_out</OutDir>
      </PropertyGroup>
      <ItemDefinitionGroup>
      </ItemDefinitionGroup>
      <ItemGroup>
        <Content Include="$(ProjectDir)main.exe">
          <CopyToOutputDirectory>PreserveNewest</CopyToOutputDirectory>
        </Content>
      </ItemGroup>
      <Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />
    </Project>
    """

    client.save({"conanfile.py": conanfile,
                 "configure.ac": configure_ac,
                 "Makefile.am": makefile_am,
                 "main.cpp": main,
                 "profile_win": profile_win,
                 "MyProject.vcxproj": my_vcxproj})
    client.run("build . -pr=profile_win")
    # Run application in msbuild output directory
    client.run_command(os.path.join("msbuild_out", "main.exe"))
    check_exe_run(client.out, "main", "msvc", None, "Release", "x86_64", None)

    bat_contents = client.load("conanbuild.bat")
    assert "conanvcvars.bat" in bat_contents
