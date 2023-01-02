from jinja2 import Template

sln_file = r"""
Microsoft Visual Studio Solution File, Format Version 12.00
# Visual Studio 15
VisualStudioVersion = 15.0.28307.757
MinimumVisualStudioVersion = 10.0.40219.1
Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "{{name}}", "{{name}}.vcxproj", "{6F392A05-B151-490C-9505-B2A49720C4D9}"
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
    EndGlobalSection
    GlobalSection(SolutionProperties) = preSolution
        HideSolutionNode = FALSE
    EndGlobalSection
    GlobalSection(ExtensibilityGlobals) = postSolution
        SolutionGuid = {DE6E462F-E299-4F9C-951A-F9404EB51521}
    EndGlobalSection
EndGlobal
"""

vcxproj = r"""<?xml version="1.0" encoding="utf-8"?>
<Project DefaultTargets="Build" ToolsVersion="15.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
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
    <RootNamespace>{{name}}</RootNamespace>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />
  <ImportGroup Label="PropertySheets">
      <Import Project="conan\\conantoolchain.props" />
      {{dependencies}}
  </ImportGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'" Label="Configuration">
    <ConfigurationType>{{type}}</ConfigurationType>
    <UseDebugLibraries>true</UseDebugLibraries>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|Win32'" Label="Configuration">
    <ConfigurationType>{{type}}</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <WholeProgramOptimization>true</WholeProgramOptimization>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'" Label="Configuration">
    <ConfigurationType>{{type}}</ConfigurationType>
    <UseDebugLibraries>true</UseDebugLibraries>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
    <ConfigurationType>{{type}}</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <WholeProgramOptimization>true</WholeProgramOptimization>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
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
      <AdditionalIncludeDirectories>include;%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
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
      <AdditionalIncludeDirectories>include;%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
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
      <AdditionalIncludeDirectories>include;%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
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
      <AdditionalIncludeDirectories>include;%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
    </ClCompile>
    <Link>
      <SubSystem>Console</SubSystem>
      <EnableCOMDATFolding>true</EnableCOMDATFolding>
      <OptimizeReferences>true</OptimizeReferences>
      <GenerateDebugInformation>true</GenerateDebugInformation>
    </Link>
  </ItemDefinitionGroup>
  <ItemGroup>
    <ClCompile Include="src/{{name}}.cpp" />
  </ItemGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />
  <ImportGroup Label="ExtensionTargets">
  </ImportGroup>
</Project>
"""

conanfile_sources_v2 = """import os

from conan import ConanFile
from conan.tools.microsoft import MSBuildToolchain, MSBuild, vs_layout
from conan.tools.files import copy


class {{package_name}}Conan(ConanFile):
    name = "{{name}}"
    version = "{{version}}"

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False]}
    default_options = {"shared": False}

    # Sources are located in the same place as this recipe, copy them to the recipe
    exports_sources = "{{name}}.sln", "{{name}}.vcxproj", "src/*", "include/*"

    def layout(self):
        vs_layout(self)

    def generate(self):
        tc = MSBuildToolchain(self)
        tc.generate()

    def build(self):
        msbuild = MSBuild(self)
        msbuild.build("{{name}}.sln")

    def package(self):
        copy(self, "*.h", os.path.join(self.source_folder, "include"),
             dst=os.path.join(self.package_folder, "include"))
        copy(self, "*.lib", src=self.build_folder, dst=os.path.join(self.package_folder, "lib"),
             keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["{{name}}"]
"""


test_conanfile_v2 = """import os

from conan import ConanFile
from conan.tools.microsoft import MSBuildDeps, MSBuildToolchain, MSBuild, vs_layout
from conan.tools.build import cross_building


class {{package_name}}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    # VirtualBuildEnv and VirtualRunEnv can be avoided if "tools.env.virtualenv:auto_use" is defined
    # (it will be defined in Conan 2.0)
    generators = "MSBuildDeps", "VirtualBuildEnv", "VirtualRunEnv"
    apply_env = False
    test_type = "explicit"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def layout(self):
        vs_layout(self)

    def generate(self):
        tc = MSBuildToolchain(self)
        tc.generate()

    def build(self):
        msbuild = MSBuild(self)
        msbuild.build("{{name}}.sln")

    def test(self):
        if not cross_building(self):
            cmd = os.path.join(self.cpp.build.bindirs[0], "{{name}}")
            self.run(cmd, env="conanrun")
"""

source_h = """#pragma once

#ifdef _WIN32
  #define {{name}}_EXPORT __declspec(dllexport)
#else
  #define {{name}}_EXPORT
#endif

{{name}}_EXPORT void {{name}}();
"""


source_cpp = r"""#include <iostream>
#include "{{name}}.h"

void {{name}}(){
    #ifdef NDEBUG
    std::cout << "{{name}}/{{version}}: Hello World Release!\n";
    #else
    std::cout << "{{name}}/{{version}}: Hello World Debug!\n";
    #endif

    // ARCHITECTURES
    #ifdef _M_X64
    std::cout << "  {{name}}/{{version}}: _M_X64 defined\n";
    #endif

    #ifdef _M_IX86
    std::cout << "  {{name}}/{{version}}: _M_IX86 defined\n";
    #endif

    #ifdef _M_ARM64
    std::cout << "  {{name}}/{{version}}: _M_ARM64 defined\n";
    #endif

    #if __i386__
    std::cout << "  {{name}}/{{version}}: __i386__ defined\n";
    #endif

    #if __x86_64__
    std::cout << "  {{name}}/{{version}}: __x86_64__ defined\n";
    #endif

    #if __aarch64__
    std::cout << "  {{name}}/{{version}}: __aarch64__ defined\n";
    #endif

    // Libstdc++
    #if defined _GLIBCXX_USE_CXX11_ABI
    std::cout << "  {{name}}/{{version}}: _GLIBCXX_USE_CXX11_ABI "<< _GLIBCXX_USE_CXX11_ABI << "\n";
    #endif

    // COMPILER VERSIONS
    #if _MSC_VER
    std::cout << "  {{name}}/{{version}}: _MSC_VER" << _MSC_VER<< "\n";
    #endif

    #if _MSVC_LANG
    std::cout << "  {{name}}/{{version}}: _MSVC_LANG" << _MSVC_LANG<< "\n";
    #endif

    #if __cplusplus
    std::cout << "  {{name}}/{{version}}: __cplusplus" << __cplusplus<< "\n";
    #endif

    #if __INTEL_COMPILER
    std::cout << "  {{name}}/{{version}}: __INTEL_COMPILER" << __INTEL_COMPILER<< "\n";
    #endif

    #if __GNUC__
    std::cout << "  {{name}}/{{version}}: __GNUC__" << __GNUC__<< "\n";
    #endif

    #if __GNUC_MINOR__
    std::cout << "  {{name}}/{{version}}: __GNUC_MINOR__" << __GNUC_MINOR__<< "\n";
    #endif

    #if __clang_major__
    std::cout << "  {{name}}/{{version}}: __clang_major__" << __clang_major__<< "\n";
    #endif

    #if __clang_minor__
    std::cout << "  {{name}}/{{version}}: __clang_minor__" << __clang_minor__<< "\n";
    #endif

    #if __apple_build_version__
    std::cout << "  {{name}}/{{version}}: __apple_build_version__" << __apple_build_version__<< "\n";
    #endif

    // SUBSYSTEMS

    #if __MSYS__
    std::cout << "  {{name}}/{{version}}: __MSYS__" << __MSYS__<< "\n";
    #endif

    #if __MINGW32__
    std::cout << "  {{name}}/{{version}}: __MINGW32__" << __MINGW32__<< "\n";
    #endif

    #if __MINGW64__
    std::cout << "  {{name}}/{{version}}: __MINGW64__" << __MINGW64__<< "\n";
    #endif

    #if __CYGWIN__
    std::cout << "  {{name}}/{{version}}: __CYGWIN__" << __CYGWIN__<< "\n";
    #endif
}
"""


test_main = """#include "{{name}}.h"

int main() {
    {{name}}();
}
"""


def get_msbuild_lib_files(name, version, package_name="Pkg"):
    d = {"name": name, "version": version, "pkg_name": package_name, "type": "StaticLibrary",
         "dependencies": ""}
    sln = Template(sln_file, keep_trailing_newline=True).render(d)
    vcp = Template(vcxproj, keep_trailing_newline=True).render(d)
    conanfile = Template(conanfile_sources_v2, keep_trailing_newline=True).render(d)
    test_d = {"name": "test_" + name, "version": version, "pkg_name": package_name,
              "type": "Application",
              "dependencies": '<Import Project="conan\\conandeps.props" />'}
    test_sln = Template(sln_file, keep_trailing_newline=True).render(test_d)
    test_vcp = Template(vcxproj, keep_trailing_newline=True).render(test_d)
    test_conanfile = Template(test_conanfile_v2, keep_trailing_newline=True).render(test_d)
    files = {"conanfile.py": conanfile,
             "src/{}.cpp".format(name): Template(source_cpp, keep_trailing_newline=True).render(d),
             "include/{}.h".format(name): Template(source_h, keep_trailing_newline=True).render(d),
             "{}.sln".format(name): sln,
             "{}.vcxproj".format(name): vcp,
             "test_package/conanfile.py": test_conanfile,
             "test_package/src/test_{}.cpp".format(name):
                 Template(test_main, keep_trailing_newline=True).render({"name": name}),
             "test_package/test_{}.sln".format(name): test_sln,
             "test_package/test_{}.vcxproj".format(name): test_vcp
             }
    return files


conanfile_exe = """import os

from conan import ConanFile
from conan.tools.microsoft import MSBuildToolchain, MSBuild, vs_layout
from conan.tools.files import copy


class {{package_name}}Conan(ConanFile):
    name = "{{name}}"
    version = "{{version}}"

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"

    # Sources are located in the same place as this recipe, copy them to the recipe
    exports_sources = "{{name}}.sln", "{{name}}.vcxproj", "src/*"

    def layout(self):
        vs_layout(self)

    def generate(self):
        tc = MSBuildToolchain(self)
        tc.generate()

    def build(self):
        msbuild = MSBuild(self)
        msbuild.build("{{name}}.sln")

    def package(self):
        copy(self, "*{{name}}.exe", src=self.build_folder,
             dst=os.path.join(self.package_folder, "bin"), keep_path=False)
"""


test_conanfile_exe_v2 = """import os
from conan import ConanFile
from conan.tools.build import cross_building
from conan.tools.layout import basic_layout


class {{package_name}}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    # VirtualRunEnv can be avoided if "tools.env.virtualenv:auto_use" is defined
    # (it will be defined in Conan 2.0)
    generators = "VirtualRunEnv"
    apply_env = False
    test_type = "explicit"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def layout(self):
        basic_layout(self)

    def test(self):
        if not cross_building(self):
            self.run("{{name}}", env="conanrun")
"""

test_exe = r"""#include <iostream>

int main() {
    #ifdef NDEBUG
    std::cout << "{{name}}/{{version}}: Hello World Release!\n";
    #else
    std::cout << "{{name}}/{{version}}: Hello World Debug!\n";
    #endif
}
"""


def get_msbuild_exe_files(name, version, package_name="Pkg"):
    d = {"name": name, "version": version, "pkg_name": package_name, "type": "Application",
         "dependencies": ""}
    sln = Template(sln_file, keep_trailing_newline=True).render(d)
    vcp = Template(vcxproj, keep_trailing_newline=True).render(d)
    conanfile = Template(conanfile_exe, keep_trailing_newline=True).render(d)
    main = Template(test_exe, keep_trailing_newline=True).render(d)
    test_conanfile = Template(test_conanfile_exe_v2, keep_trailing_newline=True).render(d)
    files = {"conanfile.py": conanfile,
             "src/{}.cpp".format(name): main,
             "{}.sln".format(name): sln,
             "{}.vcxproj".format(name): vcp,
             "test_package/conanfile.py": test_conanfile
             }

    return files
