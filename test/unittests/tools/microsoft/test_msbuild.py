import os
import textwrap

import pytest

from conan import ConanFile
from conan.tools.microsoft import MSBuild, MSBuildToolchain, is_msvc, is_msvc_static_runtime
from conans.model.conf import ConfDefinition, Conf
from conans.model.settings import Settings
from conan.test.utils.mocks import MockSettings, ConanFileMock, MockOptions
from conan.test.utils.test_files import temp_folder
from conans.util.files import load


def test_msbuild_targets():
    c = ConfDefinition()
    settings = MockSettings({"build_type": "Release",
                             "compiler": "gcc",
                             "compiler.version": "7",
                             "os": "Linux",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.conf = c.get_conanfile_conf(None)

    msbuild = MSBuild(conanfile)
    cmd = msbuild.command('project.sln', targets=["static", "shared"])

    assert '/target:static;shared' in cmd


def test_msbuild_cpu_count():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.microsoft.msbuild:max_cpu_count=23
    """))

    settings = MockSettings({"build_type": "Release",
                             "compiler": "gcc",
                             "compiler.version": "7",
                             "os": "Linux",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.conf = c.get_conanfile_conf(None)

    msbuild = MSBuild(conanfile)
    cmd = msbuild.command('project.sln')

    assert '/m:23' in cmd


def test_msbuild_toolset():
    settings = Settings({"build_type": ["Release"],
                         "compiler": {"msvc": {"version": ["193"], "toolset": [None, "v142_xp"]}},
                         "os": ["Windows"],
                         "arch": ["x86_64"]})
    conanfile = ConanFile(None)
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.settings = settings
    conanfile.settings.build_type = "Release"
    conanfile.settings.compiler = "msvc"
    conanfile.settings.compiler.version = "193"
    conanfile.settings.os = "Windows"
    conanfile.settings.arch = "x86_64"

    msbuild = MSBuildToolchain(conanfile)
    assert 'v143' in msbuild.toolset

    conanfile.settings.compiler.toolset = "v142_xp"
    msbuild = MSBuildToolchain(conanfile)
    assert 'v142_xp' in msbuild.toolset


@pytest.mark.parametrize("mode,expected_toolset", [
    ("icx", "Intel C++ Compiler 2021"),
    ("dpcpp", "Intel(R) oneAPI DPC++ Compiler"),
    ("classic", "Intel C++ Compiler 19.2")
])
def test_msbuild_toolset_for_intel_cc(mode, expected_toolset):
    conanfile = ConanFile()
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.settings = Settings({"build_type": ["Release"],
                         "compiler": {"intel-cc": {"version": ["2021.3"], "mode": [mode]},
                                      "msvc": {"version": ["193"], "cppstd": ["20"]}},
                         "os": ["Windows"],
                         "arch": ["x86_64"]})
    conanfile.settings.build_type = "Release"
    conanfile.settings.compiler = "intel-cc"
    conanfile.settings.compiler.version = "2021.3"
    conanfile.settings.compiler.mode = mode
    conanfile.settings.os = "Windows"
    conanfile.settings.arch = "x86_64"

    msbuild = MSBuildToolchain(conanfile)
    assert expected_toolset == msbuild.toolset


def test_msbuild_standard():
    test_folder = temp_folder()
    conanfile = ConanFile()
    conanfile.folders.set_base_generators(test_folder)
    conanfile.conf = Conf()
    conanfile.conf.define("tools.microsoft.msbuild:installation_path", ".")
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.settings = Settings({"build_type": ["Release"],
                                   "compiler": {"msvc": {"version": ["193"], "cppstd": ["20"],
                                                         "cstd": ["17"]}},
                                   "os": ["Windows"],
                                   "arch": ["x86_64"]})
    conanfile.settings_build = conanfile.settings
    conanfile.settings.build_type = "Release"
    conanfile.settings.compiler = "msvc"
    conanfile.settings.compiler.version = "193"
    conanfile.settings.compiler.cppstd = "20"
    conanfile.settings.compiler.cstd = "17"
    conanfile.settings.os = "Windows"
    conanfile.settings.arch = "x86_64"

    msbuild = MSBuildToolchain(conanfile)
    props_file = os.path.join(test_folder, 'conantoolchain_release_x64.props')
    msbuild.generate()
    assert '<LanguageStandard>stdcpp20</LanguageStandard>' in load(props_file)
    assert '<LanguageStandard_C>stdc17</LanguageStandard_C>' in load(props_file)


def test_resource_compile():
    test_folder = temp_folder()

    settings = Settings({"build_type": ["Release"],
                         "compiler": {"msvc": {"version": ["193"], "cppstd": ["20"]}},
                         "os": ["Windows"],
                         "arch": ["x86_64"]})
    conanfile = ConanFile()
    conanfile.folders.set_base_generators(test_folder)
    conanfile.conf = Conf()
    conanfile.conf.define("tools.microsoft.msbuild:installation_path", ".")
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.settings = settings
    conanfile.settings_build = settings
    conanfile.settings.build_type = "Release"
    conanfile.settings.compiler = "msvc"
    conanfile.settings.compiler.version = "193"
    conanfile.settings.compiler.cppstd = "20"
    conanfile.settings.os = "Windows"
    conanfile.settings.arch = "x86_64"

    msbuild = MSBuildToolchain(conanfile)
    msbuild.preprocessor_definitions["MYTEST"] = "MYVALUE"
    props_file = os.path.join(test_folder, 'conantoolchain_release_x64.props')
    msbuild.generate()
    expected = """
        <ResourceCompile>
          <PreprocessorDefinitions>
             MYTEST=MYVALUE;%(PreprocessorDefinitions)
          </PreprocessorDefinitions>
        </ResourceCompile>"""

    props_file = load(props_file)  # Remove all blanks and CR to compare
    props_file = "".join(s.strip() for s in props_file.splitlines())
    assert "".join(s.strip() for s in expected.splitlines()) in props_file


@pytest.mark.parametrize("mode,expected_toolset", [
    ("icx", "Intel C++ Compiler 2021"),
    ("dpcpp", "Intel(R) oneAPI DPC++ Compiler"),
    ("classic", "Intel C++ Compiler 19.2")
])
def test_msbuild_and_intel_cc_props(mode, expected_toolset):
    test_folder = temp_folder()
    settings = Settings({"build_type": ["Release"],
                         "compiler": {"intel-cc": {"version": ["2021.3"], "mode": [mode]},
                                      "msvc": {"version": ["193"], "cppstd": ["20"]}},
                         "os": ["Windows"],
                         "arch": ["x86_64"]})
    conanfile = ConanFile()
    conanfile.folders.set_base_generators(test_folder)
    conanfile.conf = Conf()
    conanfile.conf.define("tools.intel:installation_path", "my/intel/oneapi/path")
    conanfile.conf.define("tools.microsoft.msbuild:installation_path", ".")
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.settings = settings
    conanfile.settings.build_type = "Release"
    conanfile.settings.compiler = "intel-cc"
    conanfile.settings.compiler.version = "2021.3"
    conanfile.settings.compiler.mode = mode
    conanfile.settings.os = "Windows"
    conanfile.settings.arch = "x86_64"

    msbuild = MSBuildToolchain(conanfile)
    props_file = os.path.join(test_folder, 'conantoolchain_release_x64.props')
    msbuild.generate()
    assert '<PlatformToolset>%s</PlatformToolset>' % expected_toolset in load(props_file)


@pytest.mark.parametrize("compiler,expected", [
    ("msvc", True),
    ("clang", False)
])
def test_is_msvc(compiler, expected):
    settings = Settings({"build_type": ["Release"],
                         "compiler": {compiler: {"version": ["2022"]}},
                         "os": ["Windows"],
                         "arch": ["x86_64"]})
    conanfile = ConanFile()
    conanfile.settings = settings
    conanfile.settings.compiler = compiler
    assert is_msvc(conanfile) == expected


def test_is_msvc_build():
    settings = Settings({"build_type": ["Release"],
                         "compiler": ["gcc", "msvc"],
                         "os": ["Windows"],
                         "arch": ["x86_64"]})
    conanfile = ConanFile()
    conanfile.settings = settings
    conanfile.settings.compiler = "gcc"
    conanfile.settings_build = conanfile.settings.copy()
    conanfile.settings_build.compiler = "msvc"
    assert is_msvc(conanfile) is False
    assert is_msvc(conanfile, build_context=True) is True


@pytest.mark.parametrize("compiler,shared,runtime,build_type,expected", [
    ("msvc", True, "static", "Release", True),
    ("msvc", True, "static", "Debug", True),
    ("clang", True, None, "Debug", False),
])
def test_is_msvc_static_runtime(compiler, shared, runtime, build_type, expected):
    options = MockOptions({"shared": shared})
    settings = MockSettings({"build_type": build_type,
                             "arch": "x86_64",
                             "compiler": compiler,
                             "compiler.runtime": runtime,
                             "compiler.version": "17",
                             "cppstd": "17"})
    conanfile = ConanFileMock(settings, options)
    assert is_msvc_static_runtime(conanfile) == expected


def test_msbuildtoolchain_changing_flags_via_attributes():
    test_folder = temp_folder()
    settings = Settings({"build_type": ["Release"],
                         "compiler": {"msvc": {"version": ["193"], "cppstd": ["20"]}},
                         "os": ["Windows"],
                         "arch": ["x86_64"]})
    conanfile = ConanFile()
    conanfile.settings = settings
    conanfile.folders.set_base_generators(test_folder)
    conanfile.conf = Conf()
    conanfile.conf.define_path("tools.microsoft.msbuild:installation_path", ".")
    conanfile.settings_build = settings
    conanfile.settings.build_type = "Release"
    conanfile.settings.compiler = "msvc"
    conanfile.settings.compiler.version = "193"
    conanfile.settings.compiler.cppstd = "20"
    conanfile.settings.os = "Windows"
    conanfile.settings.arch = "x86_64"

    msbuild = MSBuildToolchain(conanfile)
    msbuild.cxxflags.append("/flag1")
    msbuild.cflags.append("/flag2")
    msbuild.ldflags.append("/link1")
    msbuild.generate()
    toolchain = load(os.path.join(test_folder, "conantoolchain_release_x64.props"))

    expected_cl_compile = """
    <ClCompile>
      <PreprocessorDefinitions>%(PreprocessorDefinitions)</PreprocessorDefinitions>
      <AdditionalOptions>/flag1 /flag2 %(AdditionalOptions)</AdditionalOptions>"""
    expected_link = """
    <Link>
      <AdditionalOptions>/link1 %(AdditionalOptions)</AdditionalOptions>
    </Link>"""
    expected_resource_compile = """
    <ResourceCompile>
      <PreprocessorDefinitions>%(PreprocessorDefinitions)</PreprocessorDefinitions>
    </ResourceCompile>"""
    assert expected_cl_compile in toolchain
    assert expected_link in toolchain
    assert expected_resource_compile in toolchain
