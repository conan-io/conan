import os
import platform
import textwrap
import unittest

import pytest
from parameterized import parameterized_class

from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.pkg_cmake import pkg_cmake
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.assets.visual_project_files import get_vs_project_files
from conans.test.conftest import tools_locations
from conans.test.utils.tools import TestClient

sln_file = r"""
Microsoft Visual Studio Solution File, Format Version 12.00
# Visual Studio 15
VisualStudioVersion = 15.0.28307.757
MinimumVisualStudioVersion = 10.0.40219.1
Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "MyProject", "MyProject\MyProject.vcxproj", "{6F392A05-B151-490C-9505-B2A49720C4D9}"
EndProject
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

myproject_vcxproj = r"""<?xml version="1.0" encoding="utf-8"?>
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
    <ProjectGuid>{6F392A05-B151-490C-9505-B2A49720C4D9}</ProjectGuid>
    <Keyword>Win32Proj</Keyword>
    <RootNamespace>MyProject</RootNamespace>
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
    <Import Project="..\conan_Hello3.props" />
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
    <ClCompile Include="MyProject.cpp" />
  </ItemGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />
  <ImportGroup Label="ExtensionTargets">
  </ImportGroup>
</Project>
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
    <Import Project="..\conan_Hello1.props" />
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


vs_versions = [{"vs_version": "15", "msvc_version": "191", "ide_year": "2017", "toolset": "v141"}]

if "17" in tools_locations['visual_studio'] and not tools_locations['visual_studio']['17'].get('disabled', False):
    vs_versions.append({"vs_version": "17", "msvc_version": "19.3", "ide_year": "2022", "toolset": "v143"})


@parameterized_class(vs_versions)
@pytest.mark.tool_visual_studio
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
class MSBuildGeneratorTest(unittest.TestCase):

    @pytest.mark.slow
    @pytest.mark.tool_cmake
    def test_msbuild_generator(self):
        client = TestClient()
        client.save(pkg_cmake("Hello0", "1.0"))
        client.run("create . ")
        client.save(pkg_cmake("Hello3", "1.0"), clean_first=True)
        client.run("create . ")
        client.save(pkg_cmake("Hello1", "1.0", ["Hello0/1.0"]), clean_first=True)
        client.run("create . ")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, MSBuild
            class HelloConan(ConanFile):
                settings = "os", "build_type", "compiler", "arch"
                requires = "Hello1/1.0", "Hello3/1.0"
                generators = "MSBuildDeps"
                def build(self):
                    msbuild = MSBuild(self)
                    msbuild.build("MyProject.sln")
            """)
        myapp_cpp = gen_function_cpp(name="main", msg="MyApp",
                                     includes=["Hello1"], calls=["Hello1"])
        myproject_cpp = gen_function_cpp(name="main", msg="MyProject", includes=["Hello3"],
                                         calls=["Hello3"])
        files = {"MyProject.sln": sln_file,
                 "MyProject/MyProject.vcxproj": myproject_vcxproj,
                 "MyProject/MyProject.cpp": myproject_cpp,
                 "MyApp/MyApp.vcxproj": myapp_vcxproj,
                 "MyApp/MyApp.cpp": myapp_cpp,
                 "conanfile.py": conanfile}

        client.save(files, clean_first=True)
        client.run("install .")
        client.run("build .")
        self.assertNotIn("warning MSB4011", client.out)
        client.run_command(r"x64\Release\MyProject.exe")
        self.assertIn("MyProject: Release!", client.out)
        self.assertIn("Hello3: Release!", client.out)
        client.run_command(r"x64\Release\MyApp.exe")
        self.assertIn("MyApp: Release!", client.out)
        self.assertIn("Hello0: Release!", client.out)
        self.assertIn("Hello1: Release!", client.out)

    def test_install_reference(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . mypkg/0.1@")
        client.run("install mypkg/0.1@ -g MSBuildDeps")
        self.assertIn("Generator 'MSBuildDeps' calling 'generate()'", client.out)
        # https://github.com/conan-io/conan/issues/8163
        props = client.load("conan_mypkg_vars_release_x64.props")  # default Release/x64
        folder = props[props.find("<ConanmypkgRootFolder>")+len("<ConanmypkgRootFolder>")
                       :props.find("</ConanmypkgRootFolder>")]
        self.assertTrue(os.path.isfile(os.path.join(folder, "conaninfo.txt")))

    def test_install_reference_gcc(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . pkg/1.0@")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                generators = "MSBuildDeps"
                requires = "pkg/1.0"
            """)
        client.save({"conanfile.py": conanfile})

        client.run('install . -s os=Windows -s compiler="Visual Studio" '
                   '-s compiler.version={vs_version}'
                   ' -s compiler.runtime=MD'.format(vs_version=self.vs_version))
        self.assertIn("conanfile.py: Generator 'MSBuildDeps' calling 'generate()'", client.out)
        props = client.load("conan_pkg_release_x64.props")
        self.assertIn('<?xml version="1.0" encoding="utf-8"?>', props)
        # This will overwrite the existing one, cause configuration and arch is the same
        client.run("install . -s os=Linux -s compiler=gcc -s compiler.version=5.2 '"
                   "'-s compiler.libcxx=libstdc++")
        self.assertIn("conanfile.py: Generator 'MSBuildDeps' calling 'generate()'", client.out)
        pkg_props = client.load("conan_pkg.props")
        self.assertIn('Project="conan_pkg_release_x64.props"', pkg_props)

    def test_no_build_type_error(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . mypkg/0.1@")
        client.run("install mypkg/0.1@ -g msbuild -s build_type=None", assert_error=True)
        self.assertIn("The 'msbuild' generator requires a 'build_type' setting value", client.out)

    def test_custom_configuration(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . pkg/1.0@")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.microsoft import MSBuildDeps
            class Pkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                requires = "pkg/1.0"
                def generate(self):
                    ms = MSBuildDeps(self)
                    ms.configuration = "My"+str(self.settings.build_type)
                    ms.platform = "My"+str(self.settings.arch)
                    ms.generate()
            """)
        client.save({"conanfile.py": conanfile})

        client.run('install . -s os=Windows -s compiler="Visual Studio" '
                   '-s compiler.version={vs_version}'
                   ' -s compiler.runtime=MD'.format(vs_version=self.vs_version))
        props = client.load("conan_pkg_myrelease_myx86_64.props")
        self.assertIn('<?xml version="1.0" encoding="utf-8"?>', props)
        client.run('install . -s os=Windows -s compiler="Visual Studio" '
                   '-s compiler.version={vs_version}'
                   ' -s compiler.runtime=MD -s arch=x86 '
                   '-s build_type=Debug'.format(vs_version=self.vs_version))
        props = client.load("conan_pkg_mydebug_myx86.props")
        self.assertIn('<?xml version="1.0" encoding="utf-8"?>', props)
        props = client.load("conan_pkg.props")
        self.assertIn("conan_pkg_myrelease_myx86_64.props", props)
        self.assertIn("conan_pkg_mydebug_myx86.props", props)

    def test_custom_configuration_errors(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . pkg/1.0@")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.microsoft import MSBuildDeps
            class Pkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                requires = "pkg/1.0"
                def generate(self):
                    ms = MSBuildDeps(self)
                    ms.configuration = None
                    ms.generate()
            """)
        client.save({"conanfile.py": conanfile})

        client.run('install . -s os=Windows -s compiler="Visual Studio"'
                   ' -s compiler.version={vs_version}'
                   ' -s compiler.runtime=MD'.format(vs_version=self.vs_version), assert_error=True)
        self.assertIn("MSBuildDeps.configuration is None, it should have a value", client.out)
        client.save({"conanfile.py": conanfile.replace("configuration", "platform")})

        client.run('install . -s os=Windows -s compiler="Visual Studio"'
                   ' -s compiler.version={vs_version}'
                   ' -s compiler.runtime=MD'.format(vs_version=self.vs_version), assert_error=True)
        self.assertIn("MSBuildDeps.platform is None, it should have a value", client.out)

    def test_install_transitive(self):
        # https://github.com/conan-io/conan/issues/8065
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . pkga/1.0@")
        client.save({"conanfile.py": GenConanfile().with_requires("pkga/1.0")})
        client.run("create . pkgb/1.0@")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, MSBuild
            class HelloConan(ConanFile):
                settings = "os", "build_type", "compiler", "arch"
                requires = "pkgb/1.0@", "pkga/1.0"
                generators = "msbuild"
                def build(self):
                    msbuild = MSBuild(self)
                    msbuild.build("MyProject.sln")
            """)
        myapp_cpp = gen_function_cpp(name="main", msg="MyApp")
        myproject_cpp = gen_function_cpp(name="main", msg="MyProject")
        files = {"MyProject.sln": sln_file,
                 "MyProject/MyProject.vcxproj": myproject_vcxproj.replace("conan_Hello3.props",
                                                                          "conandeps.props"),
                 "MyProject/MyProject.cpp": myproject_cpp,
                 "MyApp/MyApp.vcxproj": myapp_vcxproj.replace("conan_Hello1.props",
                                                              "conandeps.props"),
                 "MyApp/MyApp.cpp": myapp_cpp,
                 "conanfile.py": conanfile}

        client.save(files, clean_first=True)
        client.run("install .")
        self.assertIn("'msbuild' has been deprecated and moved.", client.out)
        client.run("build .")
        self.assertNotIn("warning MSB4011", client.out)

    def test_install_build_requires(self):
        # https://github.com/conan-io/conan/issues/8170
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . tool/1.0@")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, load
            class HelloConan(ConanFile):
                settings = "os", "build_type", "compiler", "arch"
                build_requires = "tool/1.0"
                generators = "MSBuildDeps"
                def build(self):
                    deps = load("conandeps.props")
                    assert "conan_tool.props" not in deps
                    self.output.info("Conan_tools.props not in deps")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        deps = client.load("conandeps.props")
        self.assertNotIn("conan_tool.props", deps)
        client.run("create . pkg/0.1@")
        self.assertIn("Conan_tools.props not in deps", client.out)

    def test_install_transitive_build_requires(self):
        # https://github.com/conan-io/conan/issues/8170
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . dep/1.0@")
        client.run("export . tool_build/1.0@")
        client.run("export . tool_test/1.0@")
        conanfile = GenConanfile().with_requires("dep/1.0").with_build_requires("tool_build/1.0").\
            with_build_requirement("tool_test/1.0", force_host_context=True)
        client.save({"conanfile.py": conanfile})
        client.run("export . pkg/1.0@")

        client.save({"conanfile.py": GenConanfile().
                    with_settings("os", "compiler", "arch", "build_type").
                    with_requires("pkg/1.0")}, clean_first=True)
        client.run("install . -g MSBuildDeps -pr:b=default -pr:h=default --build=missing")
        pkg = client.load("conan_pkg_release_x64.props")
        assert "conan_dep.props" in pkg
        assert "tool_test" not in pkg  # test requires are not there
        assert "tool_build" not in pkg


@pytest.mark.parametrize("pattern,exclude_a,exclude_b",
                         [("['*']", True, True),
                          ("['pkga']", True, False),
                          ("['pkgb']", False, True),
                          ("['pkg*']", True, True),
                          ("['pkga', 'pkgb']", True, True),
                          ("['*a', '*b']", True, True),
                          ("['nonexist']", False, False),
                          ])
def test_exclude_code_analysis(pattern, exclude_a, exclude_b):
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . pkga/1.0@")
    client.run("create . pkgb/1.0@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.microsoft import MSBuild

        class HelloConan(ConanFile):
            settings = "os", "build_type", "compiler", "arch"
            requires = "pkgb/1.0@", "pkga/1.0"
            generators = "msbuild"
            def build(self):
                msbuild = MSBuild(self)
                msbuild.build("MyProject.sln")
        """)
    profile = textwrap.dedent("""
        include(default)
        [settings]
        build_type=Release
        arch=x86_64
        [conf]
        tools.microsoft.msbuilddeps:exclude_code_analysis = %s
        """ % pattern)

    client.save({"conanfile.py": conanfile,
                 "profile": profile})
    client.run("install . --profile profile")
    depa = client.load("conan_pkga_release_x64.props")
    depb = client.load("conan_pkgb_release_x64.props")

    if exclude_a:
        inc = "$(ConanpkgaIncludeDirectories)"
        ca_exclude = "<CAExcludePath>%s;$(CAExcludePath)</CAExcludePath>" % inc
        assert ca_exclude in depa
    else:
        assert "CAExcludePath" not in depa

    if exclude_b:
        inc = "$(ConanpkgbIncludeDirectories)"
        ca_exclude = "<CAExcludePath>%s;$(CAExcludePath)</CAExcludePath>" % inc
        assert ca_exclude in depb
    else:
        assert "CAExcludePath" not in depb


@pytest.mark.tool_visual_studio(version="15")
@pytest.mark.tool_cmake
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
def test_build_vs_project_with_a_vs2017():
    check_build_vs_project_with_a("15")


@pytest.mark.tool_visual_studio(version="17")
@pytest.mark.tool_cmake
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
def test_build_vs_project_with_a_vs2022():
    check_build_vs_project_with_a("17")


def check_build_vs_project_with_a(vs_version):
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . updep.pkg.team/0.1@")
    conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake
        class HelloConan(ConanFile):
            settings = "os", "build_type", "compiler", "arch"
            exports = '*'
            requires = "updep.pkg.team/0.1@"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                self.copy("*.h", dst="include")
                self.copy("*.a", dst="lib", keep_path=False)

            def package_info(self):
                self.cpp_info.libs = ["hello.a"]
        """)
    hello_cpp = gen_function_cpp(name="hello")
    hello_h = gen_function_h(name="hello")
    cmake = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(MyLib CXX)

        set(CMAKE_STATIC_LIBRARY_SUFFIX ".a")
        add_library(hello hello.cpp)
        """)

    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": cmake,
                 "hello.cpp": hello_cpp,
                 "hello.h": hello_h})
    client.run('create . mydep.pkg.team/0.1@ -s compiler="Visual Studio"'
               ' -s compiler.version={vs_version}'.format(vs_version=vs_version))

    consumer = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.microsoft import MSBuild

        class HelloConan(ConanFile):
            settings = "os", "build_type", "compiler", "arch"
            requires = "mydep.pkg.team/0.1@"
            generators = "MSBuildDeps", "MSBuildToolchain"
            def build(self):
                msbuild = MSBuild(self)
                msbuild.build("MyProject.sln")
        """)
    files = get_vs_project_files()
    main_cpp = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    files["MyProject/main.cpp"] = main_cpp
    files["conanfile.py"] = consumer
    props = os.path.join(client.current_folder, "conandeps.props")
    old = r'<Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />'
    new = old + '<Import Project="{props}" />'.format(props=props)
    files["MyProject/MyProject.vcxproj"] = files["MyProject/MyProject.vcxproj"].replace(old, new)
    client.save(files, clean_first=True)
    client.run('install . -s compiler="Visual Studio"'
               ' -s compiler.version={vs_version}'.format(vs_version=vs_version))
    client.run("build .")
    client.run_command(r"x64\Release\MyProject.exe")
    assert "hello: Release!" in client.out
    # TODO: This doesnt' work because get_vs_project_files() don't define NDEBUG correctly
    # assert "main: Release!" in client.out


@pytest.mark.tool_visual_studio(version="15")
@pytest.mark.tool_cmake
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
def test_build_vs_project_with_test_requires_vs2017():
    check_build_vs_project_with_test_requires("15")


@pytest.mark.tool_visual_studio(version="17")
@pytest.mark.tool_cmake
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
def test_build_vs_project_with_test_requires_vs2022():
    check_build_vs_project_with_test_requires("17")


def check_build_vs_project_with_test_requires(vs_version):
    client = TestClient()
    client.save(pkg_cmake("updep.pkg.team", "0.1"))
    client.run("create .  -s compiler.version={vs_version}".format(vs_version=vs_version))

    client.save(pkg_cmake("mydep.pkg.team", "0.1", requires=["updep.pkg.team/0.1"]),
                clean_first=True)
    client.run("create .  -s compiler.version={vs_version}".format(vs_version=vs_version))

    consumer = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.microsoft import MSBuild

        class HelloConan(ConanFile):
            settings = "os", "build_type", "compiler", "arch"
            generators = "MSBuildDeps", "MSBuildToolchain"

            def build_requirements(self):
                self.build_requires("mydep.pkg.team/0.1", force_host_context=True)

            def build(self):
                msbuild = MSBuild(self)
                msbuild.build("MyProject.sln")
        """)
    files = get_vs_project_files()
    main_cpp = gen_function_cpp(name="main", includes=["mydep_pkg_team"], calls=["mydep_pkg_team"])
    files["MyProject/main.cpp"] = main_cpp
    files["conanfile.py"] = consumer
    props = os.path.join(client.current_folder, "conandeps.props")
    old = r'<Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />'
    new = old + '<Import Project="{props}" />'.format(props=props)
    files["MyProject/MyProject.vcxproj"] = files["MyProject/MyProject.vcxproj"].replace(old, new)
    client.save(files, clean_first=True)
    client.run('install .  -s compiler.version={vs_version}'.format(vs_version=vs_version))
    client.run("build .")
    client.run_command(r"x64\Release\MyProject.exe")
    assert "mydep_pkg_team: Release!" in client.out
    assert "updep_pkg_team: Release!" in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
def test_private_transitive():
    # https://github.com/conan-io/conan/issues/9514
    client = TestClient()
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": GenConanfile().with_require("dep/0.1", private=True),
                 "consumer/conanfile.py": GenConanfile().with_requires("pkg/0.1")
                                                        .with_settings("os", "build_type", "arch")})
    client.run("create dep dep/0.1@")
    client.run("create pkg pkg/0.1@")
    client.run("install consumer -g MSBuildDeps -s arch=x86_64 -s build_type=Release")
    assert "dep/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Skip" in client.out
    deps_props = client.load("conandeps.props")
    assert "conan_pkg.props" in deps_props
    assert "dep" not in deps_props

    pkg_data_props = client.load("conan_pkg_release_x64.props")
    assert "conan_dep.props" not in pkg_data_props


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
def test_build_requires():
    # https://github.com/conan-io/conan/issues/9545
    client = TestClient()
    package = "self.copy('*', src=str(self.settings.arch), dst='bin')"
    dep = GenConanfile().with_exports("*").with_settings("arch").with_package(package)
    consumer = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.microsoft import MSBuild
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            build_requires = "dep/0.1"
            generators = "MSBuildDeps", "MSBuildToolchain"
            def build(self):
                msbuild = MSBuild(self)
                msbuild.build("hello.sln")
            """)
    hello_vcxproj = textwrap.dedent( r"""<?xml version="1.0" encoding="utf-8"?>
        <Project DefaultTargets="Build" ToolsVersion="15.0"
               xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
          <ItemGroup Label="ProjectConfigurations">
            <ProjectConfiguration Include="Release|Win32">
              <Configuration>Release</Configuration>
              <Platform>Win32</Platform>
            </ProjectConfiguration>
            <ProjectConfiguration Include="Release|x64">
              <Configuration>Release</Configuration>
              <Platform>x64</Platform>
            </ProjectConfiguration>
          </ItemGroup>
          <PropertyGroup Label="Globals">
            <VCProjectVersion>15.0</VCProjectVersion>
            <ProjectGuid>{6F392A05-B151-490C-9505-B2A49720C4D9}</ProjectGuid>
            <Keyword>Win32Proj</Keyword>
            <RootNamespace>MyProject</RootNamespace>
          </PropertyGroup>
          <Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />

          <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|Win32'" Label="Configuration">
            <ConfigurationType>Application</ConfigurationType>
            <UseDebugLibraries>false</UseDebugLibraries>
            <PlatformToolset>v141</PlatformToolset>
            <WholeProgramOptimization>true</WholeProgramOptimization>
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

          <ImportGroup Label="PropertySheets">
            <Import Project="..\conandeps.props" />
          </ImportGroup>

          <PropertyGroup Label="UserMacros" />

            <ItemGroup>
            <CustomBuild Include="data.proto">
              <FileType>Document</FileType>
              <Outputs>data.proto.h</Outputs>
              <Command>dep1tool</Command>
            </CustomBuild>
          </ItemGroup>
          <Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />
          <ImportGroup Label="ExtensionTargets">
          </ImportGroup>
        </Project>""")

    hello_sln = textwrap.dedent(r"""
        Microsoft Visual Studio Solution File, Format Version 12.00
        # Visual Studio 15
        VisualStudioVersion = 15.0.28307.757
        MinimumVisualStudioVersion = 10.0.40219.1
        Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "MyProject", "MyProject\MyProject.vcxproj", "{6F392A05-B151-490C-9505-B2A49720C4D9}"
        EndProject
        Global
            GlobalSection(SolutionConfigurationPlatforms) = preSolution
                Release|x64 = Release|x64
                Release|x86 = Release|x86
            EndGlobalSection
            GlobalSection(ProjectConfigurationPlatforms) = postSolution
                {6F392A05-B151-490C-9505-B2A49720C4D9}.Release|x64.ActiveCfg = Release|x64
                {6F392A05-B151-490C-9505-B2A49720C4D9}.Release|x64.Build.0 = Release|x64
                {6F392A05-B151-490C-9505-B2A49720C4D9}.Release|x86.ActiveCfg = Release|Win32
                {6F392A05-B151-490C-9505-B2A49720C4D9}.Release|x86.Build.0 = Release|Win32
            EndGlobalSection
            GlobalSection(SolutionProperties) = preSolution
                HideSolutionNode = FALSE
            EndGlobalSection
            GlobalSection(ExtensibilityGlobals) = postSolution
                SolutionGuid = {DE6E462F-E299-4F9C-951A-F9404EB51521}
            EndGlobalSection
        EndGlobal
        """)
    client.save({"dep/conanfile.py": dep,
                 "dep/x86/dep1tool.bat": "@echo Invoking 32bit dep_1 build tool",
                 "dep/x86_64/dep1tool.bat": "@echo Invoking 64bit dep_1 build tool",
                 "consumer/conanfile.py": consumer,
                 "consumer/hello.sln": hello_sln,
                 "consumer/MyProject/MyProject.vcxproj": hello_vcxproj,
                 "consumer/MyProject/data.proto": "dataproto"})
    client.run("create dep dep/0.1@ -s arch=x86")
    client.run("create dep dep/0.1@ -s arch=x86_64")
    with client.chdir("consumer"):
        client.run('install . -s compiler="Visual Studio" -s compiler.version=15 '
                   " -s arch=x86_64 -s build_type=Release")
        assert "dep/0.1:c0519e2d9702ec12d057bb15adb7a02baaf18107 - Cache" in client.out
        deps_props = client.load("conandeps.props")
        assert "conan_dep_build.props" in deps_props
        client.run("build .")
        assert "Invoking 64bit dep_1 build tool" in client.out

        client.run('install . -s compiler="Visual Studio" -s compiler.version=15 '
                   " -s arch=x86 -s build_type=Release")
        client.run("build .")
        assert "Invoking 32bit dep_1 build tool" in client.out

        # Make sure it works with 2 profiles too
        client.run('install . -s compiler="Visual Studio" -s compiler.version=15 '
                   " -s arch=x86_64 -s build_type=Release -s:b os=Windows -s:h os=Windows")
        client.run("build .")
        assert "Invoking 64bit dep_1 build tool" in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
def test_build_requires_transitives():
    """ The tool-requires should not bring transitive dependencies, they will conflict and
    are useless for linking
    """
    # https://github.com/conan-io/conan/issues/10222
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "tool/conanfile.py": GenConanfile("tool", "0.1").with_requires("dep/0.1"),
            "consumer/conanfile.py":
                GenConanfile().with_settings("os", "compiler", "build_type", "arch")
                              .with_build_requires("tool/0.1")})
    c.run("create dep")
    c.run("create tool")
    c.run("install consumer -g MSBuildDeps")
    tool = c.load("conan_tool_build_release_x64.props")
    assert "conan_dep_build.props" in tool
    assert "conan_dep.props" not in tool
    tool_vars = c.load("conan_tool_build_vars_release_x64.props")
    assert "<Conantool_buildDependencies>dep_build</Conantool_buildDependencies>" in tool_vars
