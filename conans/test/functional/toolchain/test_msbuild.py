import os
import platform
import textwrap
import time
import unittest

from nose.plugins.attrib import attr
from parameterized.parameterized import parameterized

from conans.model.ref import ConanFileReference, PackageReference
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
        {6F392A05-B151-490C-9505-B2A49720C4D9}.Debug|x64.ActiveCfg = Debug|x64
        {6F392A05-B151-490C-9505-B2A49720C4D9}.Debug|x64.Build.0 = Debug|x64
        {6F392A05-B151-490C-9505-B2A49720C4D9}.Debug|x86.ActiveCfg = Debug|Win32
        {6F392A05-B151-490C-9505-B2A49720C4D9}.Debug|x86.Build.0 = Debug|Win32
        {6F392A05-B151-490C-9505-B2A49720C4D9}.Release|x64.ActiveCfg = Release|x64
        {6F392A05-B151-490C-9505-B2A49720C4D9}.Release|x64.Build.0 = Release|x64
        {6F392A05-B151-490C-9505-B2A49720C4D9}.Release|x86.ActiveCfg = Release|Win32
        {6F392A05-B151-490C-9505-B2A49720C4D9}.Release|x86.Build.0 = Release|Win32
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
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" />
  <ImportGroup Label="ExtensionSettings">
  </ImportGroup>
  <ImportGroup Label="Shared">
  </ImportGroup>
  <ImportGroup Label="PropertySheets">
    <Import Project="..\conan\conan_Hello.props" />
    <Import Project="..\conan\conan_toolchain.props" />
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


@attr("toolchain")
class Base(unittest.TestCase):

    conanfile = textwrap.dedent("""
        from conans import ConanFile, MSBuild2, MSBuildToolchain
        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1"
            generators = "msbuild"
            options = {"shared": [True, False]}
            default_options = {"shared": False}
            def toolchain(self):
                tc = MSBuildToolchain(self)
                tc.definitions["DEFINITIONS_BOTH"] = "True"
                if self.settings.build_type == "Debug":
                    tc.definitions["DEFINITIONS_CONFIG"] = "Debug"
                else:
                    tc.definitions["DEFINITIONS_CONFIG"] = "Release"
                tc.write_toolchain_files()
            def build(self):
                msbuild = MSBuild2(self)
                msbuild.build("MyProject.sln")
        """)

    app = textwrap.dedent("""
        #include <iostream>
        #include "hello.h"
        int main() {
            std::cout << "Hello: " << HELLO_MSG <<std::endl;
            #ifdef NDEBUG
            std::cout << "App: Release!" <<std::endl;
            #else
            std::cout << "App: Debug!" <<std::endl;
            #endif
            std::cout << "DEFINITIONS_BOTH: " << DEFINITIONS_BOTH << "\\n";
            std::cout << "DEFINITIONS_CONFIG: " << DEFINITIONS_CONFIG << "\\n";
        }
        """)

    def setUp(self):
        self.client = TestClient(path_with_spaces=False)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import save
            import os
            class Pkg(ConanFile):
                settings = "build_type"
                def package(self):
                    save(os.path.join(self.package_folder, "include/hello.h"),
                         '#define HELLO_MSG "%s"' % self.settings.build_type)
            """)
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . hello/0.1@ -s build_type=Debug")
        self.client.run("create . hello/0.1@ -s build_type=Release")

        # Prepare the actual consumer package
        self.client.save({"conanfile.py": self.conanfile,
                          "MyProject.sln": sln_file,
                          "MyApp/MyApp.vcxproj": myapp_vcxproj,
                          "MyApp/MyApp.cpp": self.app})
        print(self.client.current_folder)

    def _run_build(self, settings, options=None):
        # Build the profile according to the settings provided
        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)
        options = " ".join("-o %s=%s" % (k, v) for k, v in options.items()) if options else ""

        # Run the configure corresponding to this test case
        self.client.run("install . %s %s -s compiler.runtime=MT -s build_type=Release -if=conan"
                        % (settings, options))
        self.client.run("install . %s %s -s compiler.runtime=MTd -s build_type=Debug -if=conan"
                        % (settings, options))
        install_out = self.client.out
        print(install_out)
        self.client.run("build . -if=conan")
        print(self.client.out)
        return install_out

    def _modify_code(self):
        content = self.client.load("app_lib.cpp")
        content = content.replace("App:", "AppImproved:")
        self.client.save({"app_lib.cpp": content})

    def _incremental_build(self, build_type=None):
        build_directory = os.path.join(self.client.current_folder, "build").replace("\\", "/")
        with self.client.chdir(build_directory):
            self.client.run("build ..")

    def _run_app(self, build_type, msg="App"):
        command_str = "%s\\MyApp.exe" % build_type
        self.client.run_command(command_str)
        self.assertIn("Hello: %s" % build_type, self.client.out)
        self.assertIn("%s: %s!" % (msg, build_type), self.client.out)
        self.assertIn("DEFINITIONS_BOTH: True", self.client.out)
        self.assertIn("DEFINITIONS_CONFIG: %s" % build_type, self.client.out)


@unittest.skipUnless(platform.system() == "Windows", "Only for windows")
class WinTest(Base):
    @parameterized.expand([("15", "14", "x86", "v140", True),
                           ("15", "17", "x86_64", "", False)])
    def test_toolchain_win(self, version, cppstd, arch, toolset, shared):
        settings = {"compiler": "Visual Studio",
                    "compiler.version": version,
                    "compiler.toolset": toolset,
                    "compiler.cppstd": cppstd,
                    "arch": arch,
                    }
        options = {"shared": shared}
        install_out = self._run_build(settings, options)

        # FIXME: Hardcoded VS version and partial toolset check
        self.assertIn("Microsoft Visual Studio 2017", self.client.out)
        self._run_app("Debug")
        return

        opposite_build_type = "Release" if build_type == "Debug" else "Debug"
        settings["build_type"] = opposite_build_type
        self._run_build(settings, options)

        self._run_app("Release")
        self._run_app("Debug")

        self._modify_code()
        time.sleep(1)
        self._incremental_build(build_type=build_type)

        self._run_app(build_type, msg="AppImproved")
        self._incremental_build(build_type=opposite_build_type)
        self._run_app(opposite_build_type, msg="AppImproved")
