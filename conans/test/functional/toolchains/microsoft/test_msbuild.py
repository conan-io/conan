import os
import platform
import shutil
import textwrap
import unittest

import pytest
from parameterized import parameterized, parameterized_class

from conan.tools.microsoft.visual import vcvars_command
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


myapp_vcxproj = r"""<?xml version="1.0" encoding="utf-8"?>
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
    <ProjectGuid>{B58316C0-C78A-4E9B-AE8F-5D6368CE3840}</ProjectGuid>
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
"""


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


vs_versions = [{"vs_version": "15", "msvc_version": "191", "ide_year": "2017", "toolset": "v141"}]

if "17" in tools_locations['visual_studio'] and not tools_locations['visual_studio']['17'].get('disabled', False):
    vs_versions.append({"vs_version": "17", "msvc_version": "193", "ide_year": "2022", "toolset": "v143"})


@parameterized_class(vs_versions)
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
@pytest.mark.tool_visual_studio
class WinTest(unittest.TestCase):

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.microsoft import MSBuildToolchain, MSBuild, MSBuildDeps
        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1"
            options = {"shared": [True, False]}
            default_options = {"shared": False}

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
                msbuild.build("MyProject.sln")
        """)
    app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"],
                           preprocessor=["DEFINITIONS_BOTH", "DEFINITIONS_BOTH2",
                                         "DEFINITIONS_BOTH_INT", "DEFINITIONS_CONFIG",
                                         "DEFINITIONS_CONFIG2", "DEFINITIONS_CONFIG_INT"])

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

    @parameterized.expand([("Visual Studio", "15", "MT", "17"),
                           ("msvc", "191", "static", "17"),
                           ("msvc", "190", "static", "14")]
                          )
    @pytest.mark.tool_cmake
    def test_toolchain_win_vs2017(self, compiler, version, runtime, cppstd):
        if self.vs_version != "15":
            pytest.skip("test for Visual Studio 2017")
        else:
            self.check_toolchain_win(compiler, version, runtime, cppstd)

    @parameterized.expand([("Visual Studio", "17", "MT", "17"),
                           ("msvc", "193", "static", "17")]
                          )
    def test_toolchain_win_vs2022(self, compiler, version, runtime, cppstd):
        if self.vs_version != "17":
            pytest.skip("test for Visual Studio 2022")
        else:
            self.check_toolchain_win(compiler, version, runtime, cppstd)

    def check_toolchain_win(self, compiler, version, runtime, cppstd):
        client = TestClient(path_with_spaces=False)
        settings = [("compiler", compiler),
                    ("compiler.version", version),
                    ("compiler.cppstd", cppstd),
                    ("compiler.runtime", runtime),
                    ("build_type", "Release"),
                    ("arch", "x86")]

        profile = textwrap.dedent("""
            [settings]
            os=Windows

            [conf]
            tools.microsoft.msbuild:vs_version={vs_version}
            """.format(vs_version=self.vs_version))
        client.save({"myprofile": profile})
        # Build the profile according to the settings provided
        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings if v)

        client.run("new hello/0.1 -m=cmake_lib")
        client.run("create . hello/0.1@ %s" % (settings, ))

        # Prepare the actual consumer package
        client.save({"conanfile.py": self.conanfile,
                     "MyProject.sln": sln_file,
                     "MyApp/MyApp.vcxproj": myapp_vcxproj,
                     "MyApp/MyApp.cpp": self.app,
                     "myprofile": profile},
                    clean_first=True)

        # Run the configure corresponding to this test case
        client.run("install . %s -if=conan -pr=myprofile" % (settings, ))
        self.assertIn("conanfile.py: MSBuildToolchain created conantoolchain_release_win32.props",
                      client.out)
        client.run("build . -if=conan")
        self.assertIn("Visual Studio {ide_year}".format(ide_year=self.ide_year), client.out)
        self.assertIn("[vcvarsall.bat] Environment initialized for: 'x86'", client.out)

        self._run_app(client, "x86", "Release")
        self.assertIn("Hello World Release", client.out)
        compiler_version = version if compiler == "msvc" else self.msvc_version
        check_exe_run(client.out, "main", "msvc", compiler_version, "Release", "x86", cppstd,
                      {"DEFINITIONS_BOTH": 'True',
                       "DEFINITIONS_BOTH2": "True",
                       "DEFINITIONS_BOTH_INT": "123",
                       "DEFINITIONS_CONFIG": 'Release',
                       "DEFINITIONS_CONFIG2": 'Release',
                       "DEFINITIONS_CONFIG_INT": "456"})
        static_runtime = True if runtime == "static" or "MT" in runtime else False
        check_vs_runtime("Release/MyApp.exe", client, self.vs_version, build_type="Release",
                         static_runtime=static_runtime)

    @pytest.mark.tool_cmake
    def test_toolchain_win_debug(self):
        client = TestClient(path_with_spaces=False)
        settings = [("compiler",  "Visual Studio"),
                    ("compiler.version",  self.vs_version),
                    ("compiler.toolset",  "v140"),
                    ("compiler.runtime",  "MDd"),
                    ("build_type",  "Debug"),
                    ("arch",  "x86_64")]

        # Build the profile according to the settings provided
        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings if v)

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
        self.assertIn("Visual Studio {ide_year}".format(ide_year=self.ide_year), client.out)
        self.assertIn("[vcvarsall.bat] Environment initialized for: 'x64'", client.out)
        self._run_app(client, "x64", "Debug")
        self.assertIn("Hello World Debug", client.out)
        check_exe_run(client.out, "main", "msvc", "190", "Debug", "x86_64", "14",
                      {"DEFINITIONS_BOTH": 'True',
                       "DEFINITIONS_BOTH2": "True",
                       "DEFINITIONS_BOTH_INT": "123",
                       "DEFINITIONS_CONFIG": 'Debug',
                       "DEFINITIONS_CONFIG2": 'Debug',
                       "DEFINITIONS_CONFIG_INT": "234"})
        check_vs_runtime("x64/Debug/MyApp.exe", client, self.vs_version, build_type="Debug")

    @pytest.mark.tool_cmake
    def test_toolchain_win_multi(self):
        client = TestClient(path_with_spaces=False)

        settings = [("compiler", "Visual Studio"),
                    ("compiler.version", self.vs_version),
                    ("compiler.cppstd", "17")]

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
        client.save({"conanfile.py": self.conanfile,
                     "MyProject.sln": sln_file,
                     "MyApp/MyApp.vcxproj": myapp_vcxproj,
                     "MyApp/MyApp.cpp": self.app},
                    clean_first=True)

        # Run the configure corresponding to this test case
        for build_type, arch, shared in configs:
            runtime = "MT" if build_type == "Release" else "MTd"
            client.run("install . %s -s build_type=%s -s arch=%s -s compiler.runtime=%s -if=conan"
                       " -o hello:shared=%s" % (settings, build_type, arch, runtime, shared))

        vs_path = vs_installation_path(self.vs_version)
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
            self.assertIn("Visual Studio {ide_year}".format(ide_year=self.ide_year), client.out)
            self.assertIn("[vcvarsall.bat] Environment initialized for: 'x64'", client.out)

            self._run_app(client, arch, build_type, shared)
            check_exe_run(client.out, "main", "msvc", self.msvc_version, build_type, arch, "17",
                          {"DEFINITIONS_BOTH": "True",
                           "DEFINITIONS_CONFIG": build_type})

            if arch == "x86":
                command_str = "%s\\MyApp.exe" % configuration
            else:
                command_str = "x64\\%s\\MyApp.exe" % configuration
            vcvars = vcvars_command(version=self.vs_version, architecture="amd64")
            cmd = ('%s && dumpbin /dependents "%s"' % (vcvars, command_str))
            client.run_command(cmd)
            if shared:
                self.assertIn("hello.dll", client.out)
            else:
                self.assertNotIn("hello.dll", client.out)
            self.assertIn("KERNEL32.dll", client.out)


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
