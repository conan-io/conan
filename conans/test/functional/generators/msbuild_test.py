import os
import platform
import textwrap
import unittest

import pytest

from conans.test.assets.cpp_test_files import cpp_hello_conan_files
from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.sources import gen_function_cpp
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


@pytest.mark.tool_visual_studio
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
class MSBuildGeneratorTest(unittest.TestCase):

    @pytest.mark.slow
    @pytest.mark.tool_cmake
    def test_msbuild_generator(self):
        client = TestClient()
        files = cpp_hello_conan_files("Hello0", "1.0")
        client.save(files)
        client.run("create . ")
        files = cpp_hello_conan_files("Hello3", "1.0")
        client.save(files, clean_first=True)
        client.run("create . ")
        files = cpp_hello_conan_files("Hello1", "1.0", deps=["Hello0/1.0"])
        client.save(files, clean_first=True)
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
                                     includes=["helloHello1"], calls=["helloHello1"])
        myproject_cpp = gen_function_cpp(name="main", msg="MyProject", includes=["helloHello3"],
                                         calls=["helloHello3"])
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
        self.assertIn("Hello Hello3", client.out)
        client.run_command(r"x64\Release\MyApp.exe")
        self.assertIn("MyApp: Release!", client.out)
        self.assertIn("Hello Hello1", client.out)
        self.assertIn("Hello Hello0", client.out)

    def test_install_reference(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . mypkg/0.1@")
        client.run("install mypkg/0.1@ -g MSBuildDeps")
        self.assertIn("Generator 'MSBuildDeps' calling 'generate()'", client.out)
        # https://github.com/conan-io/conan/issues/8163
        props = client.load("conan_mypkg_release_x64.props")  # default Release/x64
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

        client.run('install . -s os=Windows -s compiler="Visual Studio" -s compiler.version=15'
                   ' -s compiler.runtime=MD')
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

        client.run('install . -s os=Windows -s compiler="Visual Studio" -s compiler.version=15'
                   ' -s compiler.runtime=MD')
        props = client.load("conan_pkg_myrelease_myx86_64.props")
        self.assertIn('<?xml version="1.0" encoding="utf-8"?>', props)
        client.run('install . -s os=Windows -s compiler="Visual Studio" -s compiler.version=15'
                   ' -s compiler.runtime=MD -s arch=x86 -s build_type=Debug')
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

        client.run('install . -s os=Windows -s compiler="Visual Studio" -s compiler.version=15'
                   ' -s compiler.runtime=MD', assert_error=True)
        self.assertIn("MSBuildDeps.configuration is None, it should have a value", client.out)
        client.save({"conanfile.py": conanfile.replace("configuration", "platform")})

        client.run('install . -s os=Windows -s compiler="Visual Studio" -s compiler.version=15'
                   ' -s compiler.runtime=MD', assert_error=True)
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
                    assert "conan_tool.props" in deps
                    self.output.info("Conan_tools.props in deps")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        deps = client.load("conandeps.props")
        self.assertIn("conan_tool.props", deps)
        client.run("create . pkg/0.1@")
        self.assertIn("Conan_tools.props in deps", client.out)
