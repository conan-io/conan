import os
import platform
import textwrap
import unittest

import pytest

from conans.client.tools import vs_installation_path
from conans.test.assets.sources import gen_function_cpp
from conans.test.functional.utils import check_vs_runtime, check_msc_ver
from conans.test.utils.tools import TestClient


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
    EndGlobalSection
    GlobalSection(SolutionProperties) = preSolution
        HideSolutionNode = FALSE
    EndGlobalSection
    GlobalSection(ExtensibilityGlobals) = postSolution
        SolutionGuid = {DE6E462F-E299-4F9C-951A-F9404EB51521}
    EndGlobalSection
EndGlobal
"""


myapp_vcxproj = r"""<?xml version="1.0" encoding="utf-8"?>
<Project DefaultTargets="Build" ToolsVersion="15.0"
          xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
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
    <VCProjectVersion>15.0</VCProjectVersion>
    <ProjectGuid>{B58316C0-C78A-4E9B-AE8F-5D6368CE3840}</ProjectGuid>
    <Keyword>Win32Proj</Keyword>
    <RootNamespace>MyApp</RootNamespace>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />
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
  <ImportGroup Label="PropertySheets">
    <Import Project="..\conan\conan_hello.props" />
    <Import Project="..\conan\conantoolchain.props" />
  </ImportGroup>
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
"""


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
@pytest.mark.tool_visual_studio
class WinTest(unittest.TestCase):

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.microsoft import MSBuildToolchain, MSBuild
        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1"
            generators = "msbuild"
            options = {"shared": [True, False]}
            default_options = {"shared": False}
            def generate(self):
                tc = MSBuildToolchain(self)
                tc.preprocessor_definitions["DEFINITIONS_BOTH"] = "True"
                if self.settings.build_type == "Debug":
                    tc.preprocessor_definitions["DEFINITIONS_CONFIG"] = "Debug"
                else:
                    tc.preprocessor_definitions["DEFINITIONS_CONFIG"] = "Release"
                tc.generate()

            def build(self):
                msbuild = MSBuild(self)
                msbuild.build("MyProject.sln")
        """)

    app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"],
                           preprocessor=["DEFINITIONS_BOTH", "DEFINITIONS_CONFIG"])

    def _run_app(self, client, arch, build_type, msg="main"):
        if arch == "x86":
            command_str = "%s\\MyApp.exe" % build_type
        else:
            command_str = "x64\\%s\\MyApp.exe" % build_type
        client.run_command(command_str)
        if arch == "x86":
            self.assertIn("main _M_IX86 defined", client.out)
        else:
            self.assertIn("main _M_X64 defined", client.out)
        self.assertIn("Hello World %s" % build_type, client.out)
        self.assertIn("%s: %s!" % (msg, build_type), client.out)
        self.assertIn("DEFINITIONS_BOTH: True", client.out)
        self.assertIn("DEFINITIONS_CONFIG: %s" % build_type, client.out)

    @pytest.mark.tool_cmake
    def test_toolchain_win(self):
        client = TestClient(path_with_spaces=False)
        settings = {"compiler": "Visual Studio",
                    "compiler.version": "15",
                    "compiler.cppstd": "17",
                    "compiler.runtime": "MT",
                    "build_type": "Release",
                    "arch": "x86"}

        # Build the profile according to the settings provided
        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)

        client.run("new hello/0.1 -s")
        client.run("create . hello/0.1@ %s" % (settings, ))

        # Prepare the actual consumer package
        client.save({"conanfile.py": self.conanfile,
                     "MyProject.sln": sln_file,
                     "MyApp/MyApp.vcxproj": myapp_vcxproj,
                     "MyApp/MyApp.cpp": self.app},
                    clean_first=True)

        # Run the configure corresponding to this test case
        client.run("install . %s -if=conan" % (settings, ))
        self.assertIn("conanfile.py: MSBuildToolchain created conantoolchain_release_win32.props",
                      client.out)
        client.run("build . -if=conan")

        self.assertIn("Visual Studio 2017", client.out)
        self.assertIn("[vcvarsall.bat] Environment initialized for: 'x86'", client.out)
        self._run_app(client, "x86", "Release")
        check_msc_ver("v141", client.out)
        self.assertIn("main _MSVC_LANG2017", client.out)
        check_vs_runtime("Release/MyApp.exe", client, "15", static=True, build_type="Release")

    @pytest.mark.tool_cmake
    def test_toolchain_win_debug(self):
        client = TestClient(path_with_spaces=False)
        settings = {"compiler": "Visual Studio",
                    "compiler.version": "15",
                    "compiler.toolset": "v140",
                    "compiler.runtime": "MDd",
                    "build_type": "Debug",
                    "arch": "x86_64"}

        # Build the profile according to the settings provided
        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)

        client.run("new hello/0.1 -s")
        client.run("create . hello/0.1@ %s" % (settings,))

        # Prepare the actual consumer package
        client.save({"conanfile.py": self.conanfile,
                     "MyProject.sln": sln_file,
                     "MyApp/MyApp.vcxproj": myapp_vcxproj,
                     "MyApp/MyApp.cpp": self.app},
                    clean_first=True)

        # Run the configure corresponding to this test case
        client.run("install . %s -if=conan" % (settings, ))
        self.assertIn("conanfile.py: MSBuildToolchain created conantoolchain_debug_x64.props",
                      client.out)
        client.run("build . -if=conan")
        self.assertIn("Visual Studio 2017", client.out)
        self.assertIn("[vcvarsall.bat] Environment initialized for: 'x64'", client.out)
        self._run_app(client, "x64", "Debug")
        check_msc_ver("v140", client.out)
        self.assertIn("main _MSVC_LANG2014", client.out)
        check_vs_runtime("x64/Debug/MyApp.exe", client, "15", static=False, build_type="Debug")

    @pytest.mark.tool_cmake
    def test_toolchain_win_multi(self):
        client = TestClient(path_with_spaces=False)
        settings = {"compiler": "Visual Studio",
                    "compiler.version": "15",
                    "compiler.cppstd": "17"}
        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)
        client.run("new hello/0.1 -s")
        configs = [("Release", "x86"), ("Release", "x86_64"), ("Debug", "x86"), ("Debug", "x86_64")]
        for build_type, arch in configs:
            # Build the profile according to the settings provided
            runtime = "MT" if build_type == "Release" else "MTd"
            client.run("create . hello/0.1@ %s -s build_type=%s -s arch=%s -s compiler.runtime=%s"
                       % (settings, build_type, arch, runtime))

        # Prepare the actual consumer package
        client.save({"conanfile.py": self.conanfile,
                     "MyProject.sln": sln_file,
                     "MyApp/MyApp.vcxproj": myapp_vcxproj,
                     "MyApp/MyApp.cpp": self.app},
                    clean_first=True)

        # Run the configure corresponding to this test case
        for build_type, arch in configs:
            runtime = "MT" if build_type == "Release" else "MTd"
            client.run("install . %s -s build_type=%s -s arch=%s -s compiler.runtime=%s -if=conan"
                       % (settings, build_type, arch, runtime))

        vs_path = vs_installation_path("15")
        vcvars_path = os.path.join(vs_path, "VC/Auxiliary/Build/vcvarsall.bat")

        for build_type, arch in configs:
            platform_arch = "x86" if arch == "x86" else "x64"
            cmd = ('set "VSCMD_START_DIR=%%CD%%" && '
                   '"%s" x64 && msbuild "MyProject.sln" /p:Configuration=%s '
                   '/p:Platform=%s ' % (vcvars_path, build_type, platform_arch))
            client.run_command(cmd)
            self.assertIn("Visual Studio 2017", client.out)
            self.assertIn("[vcvarsall.bat] Environment initialized for: 'x64'", client.out)
            self._run_app(client, arch, build_type)
            check_msc_ver("v141", client.out)
            self.assertIn("main _MSVC_LANG2017", client.out)
