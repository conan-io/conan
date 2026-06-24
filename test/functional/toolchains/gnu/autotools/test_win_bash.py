import platform
import textwrap
import os

import pytest

from conan.test.assets.autotools import gen_makefile_am, gen_configure_ac, gen_makefile
from conan.test.assets.genconanfile import GenConanfile
from conan.test.assets.sources import gen_function_cpp
from test.conftest import tools_locations
from test.functional.utils import check_exe_run, check_vs_runtime
from conan.test.utils.tools import TestClient, default_vs_ide_version


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
def test_autotools_bash_complete_ucrt64():
    try:
        msys2_path = tools_locations["msys2"]["system"]["path"]["Windows"]
    except KeyError:
        pytest.skip("msys2 path not defined")
    try:
        ucrt64_path = tools_locations["ucrt64"]["system"]["path"]["Windows"]
        ucrt64_path = ucrt64_path.replace("\\", "/")
    except KeyError:
        pytest.skip("ucrt64 path not defined")

    client = TestClient(path_with_spaces=False)
    profile_win = textwrap.dedent(f"""
        [settings]
        os=Windows
        compiler=gcc
        compiler.version=16
        compiler.libcxx=libstdc++
        compiler.cppstd=17
        arch=x86_64
        build_type=Release

        [conf]
        tools.microsoft.bash:subsystem=msys2-ucrt64
        tools.microsoft.bash:path={msys2_path}/bash.exe
        """)

    main = gen_function_cpp(name="main")
    makefile = gen_makefile(apps=["app"])

    conanfile = textwrap.dedent(r"""
        from conan import ConanFile
        from conan.tools.gnu import Autotools

        class TestConan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "AutotoolsToolchain"

            win_bash = True

            def build(self):
                autotools = Autotools(self)
                autotools.make()
                import os
                path = os.path.abspath(".").replace("\\", "/")
                self.run(f"{path}/app.exe")
        """)

    client.save({"conanfile.py": conanfile,
                 "Makefile": makefile,
                 "app.cpp": main,
                 "profile_win": profile_win})
    client.run("build . -pr=profile_win")
    check_exe_run(client.out, "main", "gcc", "16", "Release", "x86_64", cppstd="17",
                  cxx11_abi=0, subsystem="ucrt64")
    check_vs_runtime("app.exe", client, "15", "Debug", subsystem="ucrt64")


@pytest.mark.slow
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
@pytest.mark.tool("msys2")
@pytest.mark.tool("clang", "20")
@pytest.mark.parametrize("frontend", ("clang", "clang-cl"))
@pytest.mark.parametrize("runtime", ("static", "dynamic"))
@pytest.mark.parametrize("build_type", ("Debug", "Release"))
def test_autotools_bash_complete_clang(frontend, runtime, build_type):
    client = TestClient(path_with_spaces=False)
    # Problem is that msys2 also has clang in the path, so we need to make it explicit
    clangpath = tools_locations["clang"]["20"]["path"]["Windows"]
    # compilers
    c, cpp = ("clang", "clang++") if frontend == "clang" else ("clang-cl", "clang-cl")
    comps = f'{{"cpp":"{cpp}", "c":"{c}", "rc":"{c}"}}'

    toolset_version = {"17": "v144",
                       "18": "v145"}[str(default_vs_ide_version)]

    profile_win = textwrap.dedent(f"""
        [settings]
        os=Windows
        arch=x86_64
        build_type={build_type}
        compiler=clang
        compiler.version=20
        compiler.cppstd=14
        compiler.runtime_version={toolset_version}
        compiler.runtime={runtime}

        [conf]
        tools.build:compiler_executables={comps}
        tools.microsoft.bash:subsystem=msys2
        tools.microsoft.bash:path=bash
        tools.compilation:verbosity=verbose

        [buildenv]
        PATH=+(path){clangpath}
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
    assert "__GNUC__" not in client.out
    assert "main __clang_major__20" in client.out
    check_exe_run(client.out, "main", "clang", "20", build_type, "x86_64", None)

    bat_contents = client.load("conanbuild.bat")
    assert "conanvcvars.bat" in bat_contents

    static_runtime = runtime == "static"
    check_vs_runtime("main.exe", client, default_vs_ide_version, build_type=build_type,
                     static_runtime=static_runtime)


@pytest.mark.parametrize("scope", ["build", "run"])
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_add_msys2_path_automatically(scope):
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

    client.save_home({"global.conf": textwrap.dedent("""
            tools.microsoft.bash:subsystem=msys2
            tools.microsoft.bash:path={}
            """.format(bash_path))})

    conanfile = textwrap.dedent(f"""
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"

            def configure(self):
                if "{scope}" == "build":
                    self.win_bash = True
                else:
                    self.win_bash_run = True

            def build(self):
                self.run("ar -h", scope="{scope}")
                """)

    client.save({"conanfile.py": conanfile})
    client.run("build .")
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
    my_vcxproj = r"""<?xml version="1.0" encoding="utf-8"?>
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


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_autotools_support_custom_make():
    """ Check that the conf setting `tools.gnu:make_program` works when set with
    windows native paths. For example, when set programatically by a package
    """
    client = TestClient(path_with_spaces=False)
    bash_path = None
    make_path = None
    try:
        bash_path = tools_locations["msys2"]["system"]["path"]["Windows"] + "/bash.exe"
        make_path = tools_locations["msys2"]["system"]["path"]["Windows"] + "/make.exe"
    except KeyError:
        pytest.skip("msys2 path not defined")
    if not os.path.exists(make_path):
        pytest.skip("msys2 make not installed")

    make_path = make_path.replace("/", "\\")
    assert os.path.exists(make_path)

    profile = textwrap.dedent(f"""
        include(default)

        [conf]
        tools.microsoft.bash:subsystem=msys2
        tools.microsoft.bash:path={bash_path}
        tools.gnu:make_program={make_path}
        tools.build:compiler_executables={{"c": "cl", "cpp": "cl"}}
        """)

    # The autotools support for "cl" compiler (VS) is very limited, linking with deps doesn't
    # work but building a simple app do
    makefile = gen_makefile()

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import Autotools

        class TestConan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "AutotoolsToolchain"
            win_bash = True

            def build(self):
                # These commands will run in bash activating first the vcvars and
                # then inside the bash activating the
                autotools = Autotools(self)
                autotools.make()
        """)

    client.save({"conanfile.py": conanfile,
                 "Makefile": makefile,
                 "profile": profile})
    client.run("build . -pr=profile")
    # This used to crash, because ``make_program`` was not unix_path
    assert "conanfile.py: Calling build()" in client.out
