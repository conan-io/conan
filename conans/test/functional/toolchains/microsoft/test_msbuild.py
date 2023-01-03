import os
import platform
import textwrap

import pytest

from conan.tools.microsoft.visual import msvc_version_to_vs_ide_version, vcvars_command
from conans.client.tools import vs_installation_path
from conans.test.assets.sources import gen_function_cpp
from conans.test.conftest import tools_locations
from conans.test.functional.utils import check_vs_runtime, check_exe_run
from conans.test.utils.tools import TestClient
from conans.util.files import rmdir


sln_file = r"""
Microsoft Visual Studio Solution File, Format Version 12.00
# Visual Studio 15
VisualStudioVersion = 15.0.28307.757
MinimumVisualStudioVersion = 10.0.40219.1
Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "MyApp", "MyApp\MyApp.vcxproj", "{B58316C0-C78A-4E9B-AE8F-5D6368CE3840}"
EndProject
Global
    GlobalSection(SolutionConfigurationPlatforms) = preSolution
        Debug|x64 = Debug|x64
        Debug|x86 = Debug|x86
        Release|x64 = Release|x64
        Release|x86 = Release|x86
        ReleaseShared|x64 = ReleaseShared|x64
        ReleaseShared|x86 = ReleaseShared|x86
    EndGlobalSection
    GlobalSection(ProjectConfigurationPlatforms) = postSolution
        {B58316C0-C78A-4E9B-AE8F-5D6368CE3840}.Debug|x64.ActiveCfg = Debug|x64
        {B58316C0-C78A-4E9B-AE8F-5D6368CE3840}.Debug|x64.Build.0 = Debug|x64
        {B58316C0-C78A-4E9B-AE8F-5D6368CE3840}.Debug|x86.ActiveCfg = Debug|Win32
        {B58316C0-C78A-4E9B-AE8F-5D6368CE3840}.Debug|x86.Build.0 = Debug|Win32
        {B58316C0-C78A-4E9B-AE8F-5D6368CE3840}.Release|x64.ActiveCfg = Release|x64
        {B58316C0-C78A-4E9B-AE8F-5D6368CE3840}.Release|x64.Build.0 = Release|x64
        {B58316C0-C78A-4E9B-AE8F-5D6368CE3840}.Release|x86.ActiveCfg = Release|Win32
        {B58316C0-C78A-4E9B-AE8F-5D6368CE3840}.Release|x86.Build.0 = Release|Win32
        {B58316C0-C78A-4E9B-AE8F-5D6368CE3840}.ReleaseShared|x64.ActiveCfg = ReleaseShared|x64
        {B58316C0-C78A-4E9B-AE8F-5D6368CE3840}.ReleaseShared|x64.Build.0 = ReleaseShared|x64
        {B58316C0-C78A-4E9B-AE8F-5D6368CE3840}.ReleaseShared|x86.ActiveCfg = ReleaseShared|Win32
        {B58316C0-C78A-4E9B-AE8F-5D6368CE3840}.ReleaseShared|x86.Build.0 = ReleaseShared|Win32
    EndGlobalSection
    GlobalSection(SolutionProperties) = preSolution
        HideSolutionNode = FALSE
    EndGlobalSection
    GlobalSection(ExtensibilityGlobals) = postSolution
        SolutionGuid = {DE6E462F-E299-4F9C-951A-F9404EB51521}
    EndGlobalSection
EndGlobal
"""

def myapp_vcxproj(force_import_generated_files=False):
    intrusive_conan_integration = r"""
  <ImportGroup Label="PropertySheets">
    <Import Project="..\conan\conan_hello.props" />
    <Import Project="..\conan\conantoolchain.props" />
  </ImportGroup>
"""

    return r"""<?xml version="1.0" encoding="utf-8"?>
<Project DefaultTargets="Build" ToolsVersion="15.0"
          xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemGroup Label="ProjectConfigurations">
    <ProjectConfiguration Include="Debug|Win32">
      <Configuration>Debug</Configuration>
      <Platform>Win32</Platform>
    </ProjectConfiguration>
    <ProjectConfiguration Include="ReleaseShared|Win32">
      <Configuration>ReleaseShared</Configuration>
      <Platform>Win32</Platform>
    </ProjectConfiguration>
    <ProjectConfiguration Include="ReleaseShared|x64">
      <Configuration>ReleaseShared</Configuration>
      <Platform>x64</Platform>
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
    <VCProjectVersion>15.0</VCProjectVersion>
    <ProjectGuid>{{B58316C0-C78A-4E9B-AE8F-5D6368CE3840}}</ProjectGuid>
    <Keyword>Win32Proj</Keyword>
    <RootNamespace>MyApp</RootNamespace>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='ReleaseShared|Win32'" Label="Configuration">
    <ConfigurationType>Application</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <PlatformToolset>v141</PlatformToolset>
    <WholeProgramOptimization>true</WholeProgramOptimization>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='ReleaseShared|x64'" Label="Configuration">
    <ConfigurationType>Application</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <PlatformToolset>v141</PlatformToolset>
    <WholeProgramOptimization>true</WholeProgramOptimization>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'" Label="Configuration">
    <ConfigurationType>Application</ConfigurationType>
    <UseDebugLibraries>true</UseDebugLibraries>
    <PlatformToolset>v141</PlatformToolset>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|Win32'" Label="Configuration">
    <ConfigurationType>Application</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <PlatformToolset>v141</PlatformToolset>
    <WholeProgramOptimization>true</WholeProgramOptimization>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'" Label="Configuration">
    <ConfigurationType>Application</ConfigurationType>
    <UseDebugLibraries>true</UseDebugLibraries>
    <PlatformToolset>v141</PlatformToolset>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
    <ConfigurationType>Application</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <PlatformToolset>v141</PlatformToolset>
    <WholeProgramOptimization>true</WholeProgramOptimization>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <!-- Very IMPORTANT this should go BEFORE the Microsoft.Cpp.props.
  If it goes after, the Toolset definition is ignored -->
{}
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" />
  <ImportGroup Label="ExtensionSettings">
  </ImportGroup>
  <ImportGroup Label="Shared">
  </ImportGroup>
  <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props"
    Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')"
    Label="LocalAppDataPlatform" />
  </ImportGroup>
  <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='Release|Win32'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props"
    Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')"
    Label="LocalAppDataPlatform" />
  </ImportGroup>
   <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='ReleaseShared|x64'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props"
    Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')"
    Label="LocalAppDataPlatform" />
  </ImportGroup>
   <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='ReleaseShared|Win32'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props"
    Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')"
    Label="LocalAppDataPlatform" />
  </ImportGroup>
  <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='Debug|x64'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props"
    Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')"
    Label="LocalAppDataPlatform" />
  </ImportGroup>
  <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props"
    Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')"
    Label="LocalAppDataPlatform" />
  </ImportGroup>
  <PropertyGroup Label="UserMacros" />
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'">
    <LinkIncremental>true</LinkIncremental>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'">
    <LinkIncremental>true</LinkIncremental>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|Win32'">
    <LinkIncremental>false</LinkIncremental>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <LinkIncremental>false</LinkIncremental>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='ReleaseShared|Win32'">
    <LinkIncremental>false</LinkIncremental>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='ReleaseShared|x64'">
    <LinkIncremental>false</LinkIncremental>
  </PropertyGroup>
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'">
    <ClCompile>
      <PrecompiledHeader>NotUsing</PrecompiledHeader>
      <WarningLevel>Level3</WarningLevel>
      <Optimization>Disabled</Optimization>
      <SDLCheck>true</SDLCheck>
      <PreprocessorDefinitions>WIN32;_DEBUG;_CONSOLE;%(PreprocessorDefinitions)
      </PreprocessorDefinitions>
      <ConformanceMode>true</ConformanceMode>
    </ClCompile>
    <Link>
      <SubSystem>Console</SubSystem>
      <GenerateDebugInformation>true</GenerateDebugInformation>
    </Link>
  </ItemDefinitionGroup>
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='ReleaseShared|Win32'">
    <ClCompile>
      <PrecompiledHeader>NotUsing</PrecompiledHeader>
      <WarningLevel>Level3</WarningLevel>
      <Optimization>MaxSpeed</Optimization>
      <FunctionLevelLinking>true</FunctionLevelLinking>
      <IntrinsicFunctions>true</IntrinsicFunctions>
      <SDLCheck>true</SDLCheck>
      <PreprocessorDefinitions>WIN32;NDEBUG;_CONSOLE;%(PreprocessorDefinitions)
      </PreprocessorDefinitions>
      <ConformanceMode>true</ConformanceMode>
    </ClCompile>
    <Link>
      <SubSystem>Console</SubSystem>
      <EnableCOMDATFolding>true</EnableCOMDATFolding>
      <OptimizeReferences>true</OptimizeReferences>
      <GenerateDebugInformation>true</GenerateDebugInformation>
    </Link>
  </ItemDefinitionGroup>
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='ReleaseShared|x64'">
    <ClCompile>
      <PrecompiledHeader>NotUsing</PrecompiledHeader>
      <WarningLevel>Level3</WarningLevel>
      <Optimization>MaxSpeed</Optimization>
      <FunctionLevelLinking>true</FunctionLevelLinking>
      <IntrinsicFunctions>true</IntrinsicFunctions>
      <SDLCheck>true</SDLCheck>
      <PreprocessorDefinitions>NDEBUG;_CONSOLE;%(PreprocessorDefinitions)</PreprocessorDefinitions>
      <ConformanceMode>true</ConformanceMode>
    </ClCompile>
    <Link>
      <SubSystem>Console</SubSystem>
      <EnableCOMDATFolding>true</EnableCOMDATFolding>
      <OptimizeReferences>true</OptimizeReferences>
      <GenerateDebugInformation>true</GenerateDebugInformation>
    </Link>
  </ItemDefinitionGroup>
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'">
    <ClCompile>
      <PrecompiledHeader>NotUsing</PrecompiledHeader>
      <WarningLevel>Level3</WarningLevel>
      <Optimization>Disabled</Optimization>
      <SDLCheck>true</SDLCheck>
      <PreprocessorDefinitions>_DEBUG;_CONSOLE;%(PreprocessorDefinitions)</PreprocessorDefinitions>
      <ConformanceMode>true</ConformanceMode>
    </ClCompile>
    <Link>
      <SubSystem>Console</SubSystem>
      <GenerateDebugInformation>true</GenerateDebugInformation>
    </Link>
  </ItemDefinitionGroup>
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|Win32'">
    <ClCompile>
      <PrecompiledHeader>NotUsing</PrecompiledHeader>
      <WarningLevel>Level3</WarningLevel>
      <Optimization>MaxSpeed</Optimization>
      <FunctionLevelLinking>true</FunctionLevelLinking>
      <IntrinsicFunctions>true</IntrinsicFunctions>
      <SDLCheck>true</SDLCheck>
      <PreprocessorDefinitions>WIN32;NDEBUG;_CONSOLE;%(PreprocessorDefinitions)
      </PreprocessorDefinitions>
      <ConformanceMode>true</ConformanceMode>
    </ClCompile>
    <Link>
      <SubSystem>Console</SubSystem>
      <EnableCOMDATFolding>true</EnableCOMDATFolding>
      <OptimizeReferences>true</OptimizeReferences>
      <GenerateDebugInformation>true</GenerateDebugInformation>
    </Link>
  </ItemDefinitionGroup>
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <ClCompile>
      <PrecompiledHeader>NotUsing</PrecompiledHeader>
      <WarningLevel>Level3</WarningLevel>
      <Optimization>MaxSpeed</Optimization>
      <FunctionLevelLinking>true</FunctionLevelLinking>
      <IntrinsicFunctions>true</IntrinsicFunctions>
      <SDLCheck>true</SDLCheck>
      <PreprocessorDefinitions>NDEBUG;_CONSOLE;%(PreprocessorDefinitions)</PreprocessorDefinitions>
      <ConformanceMode>true</ConformanceMode>
    </ClCompile>
    <Link>
      <SubSystem>Console</SubSystem>
      <EnableCOMDATFolding>true</EnableCOMDATFolding>
      <OptimizeReferences>true</OptimizeReferences>
      <GenerateDebugInformation>true</GenerateDebugInformation>
    </Link>
  </ItemDefinitionGroup>
  <ItemGroup>
    <ClCompile Include="MyApp.cpp" />
  </ItemGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />
  <ImportGroup Label="ExtensionTargets">
  </ImportGroup>
</Project>
""".format("" if force_import_generated_files else intrusive_conan_integration)


@pytest.mark.tool_visual_studio(version='15')
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
def test_msvc_runtime_flag_vs2017():
    check_msvc_runtime_flag("15", "191")


@pytest.mark.tool_visual_studio(version='17')
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
def test_msvc_runtime_flag_vs2022():
    check_msvc_runtime_flag("17", "193")


def check_msvc_runtime_flag(vs_version, msvc_version):
    client = TestClient()
    conanfile = textwrap.dedent("""
       from conans import ConanFile
       from conan.tools.microsoft import msvc_runtime_flag
       class App(ConanFile):
           settings = "os", "arch", "compiler", "build_type"

           def generate(self):
               self.output.info("MSVC FLAG={}!!".format(msvc_runtime_flag(self)))
        """)
    client.save({"conanfile.py": conanfile})
    client.run('install . -s compiler="Visual Studio" -s compiler.version={vs_version} '
               '-s compiler.runtime=MD'.format(vs_version=vs_version))
    assert "MSVC FLAG=MD!!" in client.out
    client.run('install . -s compiler=msvc -s compiler.version={msvc_version} '
               '-s compiler.runtime=static '
               '-s compiler.runtime_type=Debug '
               '-s compiler.cppstd=14'.format(msvc_version=msvc_version))
    assert "MSVC FLAG=MTd!!" in client.out
    client.run('install . -s compiler=msvc -s compiler.version={msvc_version} '
               '-s compiler.runtime=dynamic '
               '-s compiler.cppstd=14'.format(msvc_version=msvc_version))
    assert "MSVC FLAG=MD!!" in client.out


def _has_tool_vc(vs_version):
    return vs_version in tools_locations["visual_studio"] and \
           not tools_locations["visual_studio"][vs_version].get("disabled", False)


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
@pytest.mark.tool_visual_studio
class TestMSBuild:

    app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"],
                           preprocessor=["DEFINITIONS_BOTH", "DEFINITIONS_BOTH2",
                                         "DEFINITIONS_BOTH_INT", "DEFINITIONS_CONFIG",
                                         "DEFINITIONS_CONFIG2", "DEFINITIONS_CONFIG_INT"])

    _vs_versions = {
        "11": {
            "msvc_version": "170",
            "ide_year": "2012",
        },
        "12": {
            "msvc_version": "180",
            "ide_year": "2013",
        },
        "14": {
            "msvc_version": "190",
            "ide_year": "2015",
        },
        "15": {
            "msvc_version": "191",
            "ide_year": "2017",
        },
        "16": {
            "msvc_version": "192",
            "ide_year": "2019",
        },
        "17": {
            "msvc_version": "193",
            "ide_year": "2022",
        },
    }

    @staticmethod
    def _conanfile(force_import_generated_files=False):
        return textwrap.dedent(f"""
            from conans import ConanFile
            from conan.tools.microsoft import MSBuildToolchain, MSBuild, MSBuildDeps
            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                requires = "hello/0.1"
                options = {{"shared": [True, False]}}
                default_options = {{"shared": False}}

                def layout(self):
                    self.folders.generators = "conan"
                    self.folders.build = "."

                def generate(self):
                    tc = MSBuildToolchain(self)
                    gen = MSBuildDeps(self)
                    if self.options["hello"].shared and self.settings.build_type == "Release":
                        tc.configuration = "ReleaseShared"
                        gen.configuration = "ReleaseShared"

                    tc.preprocessor_definitions["DEFINITIONS_BOTH"] = '"True"'
                    tc.preprocessor_definitions["DEFINITIONS_BOTH2"] = 'DEFINITIONS_BOTH'
                    tc.preprocessor_definitions["DEFINITIONS_BOTH_INT"] = 123
                    if self.settings.build_type == "Debug":
                        tc.preprocessor_definitions["DEFINITIONS_CONFIG"] = '"Debug"'
                        tc.preprocessor_definitions["DEFINITIONS_CONFIG_INT"] = 234
                    else:
                        tc.preprocessor_definitions["DEFINITIONS_CONFIG"] = '"Release"'
                        tc.preprocessor_definitions["DEFINITIONS_CONFIG_INT"] = 456
                    tc.preprocessor_definitions["DEFINITIONS_CONFIG2"] = 'DEFINITIONS_CONFIG'

                    tc.generate()
                    gen.generate()

                def imports(self):
                    if self.options["hello"].shared and self.settings.build_type == "Release":
                        configuration = "ReleaseShared"
                        if self.settings.arch == "x86_64":
                            dst = "x64/%s" % configuration
                        else:
                            dst = configuration
                    else:
                        configuration = self.settings.build_type
                        dst = "%s/%s" % (self.settings.arch, configuration)
                    self.copy("*.dll", src="bin", dst=dst, keep_path=False)

                def build(self):
                    msbuild = MSBuild(self)
                    msbuild.build("MyProject.sln", force_import_generated_files={force_import_generated_files})
        """)

    @staticmethod
    def _run_app(client, arch, build_type, shared=None):
        if build_type == "Release" and shared:
            configuration = "ReleaseShared"
        else:
            configuration = build_type

        if arch == "x86":
            command_str = "%s\\MyApp.exe" % configuration
        else:
            command_str = "x64\\%s\\MyApp.exe" % configuration
        client.run_command(command_str)

    @pytest.mark.parametrize("arch", ["x86", "x86_64"])
    @pytest.mark.parametrize(
        "compiler,version,runtime,cppstd",
        [
            pytest.param(
                "msvc", "190", "static", "14",
                marks=pytest.mark.skipif(not _has_tool_vc("14"), reason="Visual Studio 14 not installed"),
            ),
            pytest.param(
                "Visual Studio", "15", "MT", "17",
                marks=pytest.mark.skipif(not _has_tool_vc("15"), reason="Visual Studio 15 not installed"),
            ),
            pytest.param(
                "msvc", "191", "static", "17",
                marks=pytest.mark.skipif(not _has_tool_vc("15"), reason="Visual Studio 15 not installed"),
            ),
            pytest.param(
                "Visual Studio", "17", "MT", "17",
                marks=pytest.mark.skipif(not _has_tool_vc("17"), reason="Visual Studio 17 not installed"),
            ),
            pytest.param(
                "msvc", "193", "static", "17",
                marks=pytest.mark.skipif(not _has_tool_vc("17"), reason="Visual Studio 17 not installed"),
            ),
        ])
    @pytest.mark.parametrize("build_type", ["Debug", "Release"])
    @pytest.mark.parametrize("force_import_generated_files", [False, True])
    @pytest.mark.tool_cmake
    def test_toolchain_win(self, arch, compiler, version, runtime, cppstd, build_type, force_import_generated_files):
        vs_version = msvc_version_to_vs_ide_version(version) if compiler == "msvc" else version

        if compiler == "Visual Studio" and build_type == "Debug":
            runtime += "d"

        client = TestClient(path_with_spaces=False)
        settings = [("compiler", compiler),
                    ("compiler.version", version),
                    ("compiler.cppstd", cppstd),
                    ("compiler.runtime", runtime),
                    ("build_type", build_type),
                    ("arch", arch)]
        if compiler == "msvc":
            settings.append(("compiler.runtime_type", "Debug" if build_type == "Debug" else "Release"))

        profile = textwrap.dedent(f"""
            [settings]
            os=Windows

            [conf]
            tools.microsoft.msbuild:vs_version={vs_version}
            """)
        client.save({"myprofile": profile})
        # Build the profile according to the settings provided
        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings if v)

        client.run("new hello/0.1 -m=cmake_lib")
        client.run("create . hello/0.1@ %s" % (settings, ))

        # Prepare the actual consumer package
        client.save({"conanfile.py": self._conanfile(force_import_generated_files),
                     "MyProject.sln": sln_file,
                     "MyApp/MyApp.vcxproj": myapp_vcxproj(force_import_generated_files),
                     "MyApp/MyApp.cpp": self.app,
                     "myprofile": profile},
                    clean_first=True)

        # Run the configure corresponding to this test case
        client.run("install . %s -if=conan -pr=myprofile" % (settings, ))
        msbuild_arch = {
            "x86": "x86",
            "x86_64": "x64",
            "armv7": "ARM",
            "armv8": "ARM64",
        }[arch]
        props_arch = {
            "x86": "Win32",
            "x86_64": "x64",
            "armv7": "ARM",
            "armv8": "ARM64",
        }[arch]
        props_file = f"conantoolchain_{build_type.lower()}_{props_arch.lower()}.props"
        assert f"conanfile.py: MSBuildToolchain created {props_file}" in client.out
        client.run("build . -if=conan")
        assert "Visual Studio {ide_year}".format(ide_year=self._vs_versions[vs_version]["ide_year"]) in client.out
        assert f"[vcvarsall.bat] Environment initialized for: '{msbuild_arch.lower()}'" in client.out

        self._run_app(client, arch, build_type)
        assert f"Hello World {build_type}" in client.out
        compiler_version = self._vs_versions[vs_version]["msvc_version"]
        check_exe_run(client.out, "main", "msvc", compiler_version, build_type, arch, cppstd,
                      {"DEFINITIONS_BOTH": "True",
                       "DEFINITIONS_BOTH2": "True",
                       "DEFINITIONS_BOTH_INT": "123",
                       "DEFINITIONS_CONFIG": build_type,
                       "DEFINITIONS_CONFIG2": build_type,
                       "DEFINITIONS_CONFIG_INT": "234" if build_type == "Debug" else "456"})
        static_runtime = runtime == "static" or "MT" in runtime
        check_vs_runtime("{}{}/MyApp.exe".format("" if arch == "x86" else f"{msbuild_arch}/", build_type), client,
                         vs_version, build_type=build_type, static_runtime=static_runtime)

    @pytest.mark.parametrize(
        "compiler,version,runtime,cppstd",
        [
            pytest.param(
                "Visual Studio", "15", "MT", "17",
                marks=pytest.mark.skipif(not _has_tool_vc("15"), reason="Visual Studio 15 not installed"),
            ),
        ]
    )
    @pytest.mark.tool_cmake
    def test_toolchain_win_multi(self, compiler, version, runtime, cppstd):
        client = TestClient(path_with_spaces=False)

        settings = [("compiler", compiler),
                    ("compiler.version", version),
                    ("compiler.cppstd", cppstd)]

        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings if v)
        client.run("new hello/0.1 -m=cmake_lib")
        configs = [("Release", "x86", True), ("Release", "x86_64", True),
                   ("Debug", "x86", False), ("Debug", "x86_64", False)]
        for build_type, arch, shared in configs:
            # Build the profile according to the settings provided
            # TODO: It is a bit ugly to remove manually
            build_test_folder = os.path.join(client.current_folder, "test_package", "build")
            rmdir(build_test_folder)
            runtime = "MT" if build_type == "Release" else "MTd"
            client.run("create . hello/0.1@ %s -s build_type=%s -s arch=%s -s compiler.runtime=%s "
                       " -o hello:shared=%s" % (settings, build_type, arch, runtime, shared))

        # Prepare the actual consumer package
        client.save({"conanfile.py": self._conanfile(),
                     "MyProject.sln": sln_file,
                     "MyApp/MyApp.vcxproj": myapp_vcxproj(),
                     "MyApp/MyApp.cpp": self.app},
                    clean_first=True)

        # Run the configure corresponding to this test case
        for build_type, arch, shared in configs:
            runtime = "MT" if build_type == "Release" else "MTd"
            client.run("install . %s -s build_type=%s -s arch=%s -s compiler.runtime=%s -if=conan"
                       " -o hello:shared=%s" % (settings, build_type, arch, runtime, shared))

        vs_path = vs_installation_path(version)
        vcvars_path = os.path.join(vs_path, "VC/Auxiliary/Build/vcvarsall.bat")

        for build_type, arch, shared in configs:
            platform_arch = "x86" if arch == "x86" else "x64"
            if build_type == "Release" and shared:
                configuration = "ReleaseShared"
            else:
                configuration = build_type

            # The "conan build" command is not good enough, cannot do the switch between configs
            cmd = ('set "VSCMD_START_DIR=%%CD%%" && '
                   '"%s" x64 && msbuild "MyProject.sln" /p:Configuration=%s '
                   '/p:Platform=%s ' % (vcvars_path, configuration, platform_arch))
            client.run_command(cmd)
            assert "Visual Studio {ide_year}".format(self._vs_versions[version]["ide_year"]) in client.out
            assert "[vcvarsall.bat] Environment initialized for: 'x64'" in client.out

            self._run_app(client, arch, build_type, shared)
            check_exe_run(client.out, "main", "msvc", self._vs_versions[version]["msvc_version"], build_type, arch, cppstd,
                          {"DEFINITIONS_BOTH": "True",
                           "DEFINITIONS_CONFIG": build_type})

            if arch == "x86":
                command_str = "%s\\MyApp.exe" % configuration
            else:
                command_str = "x64\\%s\\MyApp.exe" % configuration
            vcvars = vcvars_command(version, architecture="amd64")
            cmd = ('%s && dumpbin /dependents "%s"' % (vcvars, command_str))
            client.run_command(cmd)
            if shared:
                assert "hello.dll" in client.out
            else:
                assert "hello.dll" not in client.out
            assert "KERNEL32.dll" in client.out


def test_msvc_runtime_flag_common_usage():
    """The msvc_runtime_flag must not break when expecting a string
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
       from conans import ConanFile
       from conan.tools.microsoft import msvc_runtime_flag
       class App(ConanFile):
           settings = "os", "arch", "compiler", "build_type"

           def validate(self):
               if "MT" in msvc_runtime_flag(self):
                   pass
        """)
    client.save({"conanfile.py": conanfile})
    client.run('info .')
