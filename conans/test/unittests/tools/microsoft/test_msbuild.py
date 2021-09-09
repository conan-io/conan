import mock
import os
import textwrap
from mock import Mock

from conan.tools.microsoft import MSBuild, MSBuildToolchain
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import ConanFileMock, MockSettings
from conans.tools import load
from conans import ConanFile, Settings


def test_msbuild_cpu_count():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.microsoft.msbuild:max_cpu_count=23
        tools.build:processes=10
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
                         "compiler": {"msvc": {"version": ["19.3"]}},
                         "os": ["Windows"],
                         "arch": ["x86_64"]})
    conanfile = ConanFile(Mock(), None)
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.initialize(settings)
    conanfile.settings.build_type = "Release"
    conanfile.settings.compiler = "msvc"
    conanfile.settings.compiler.version = "19.3"
    conanfile.settings.os = "Windows"
    conanfile.settings.arch = "x86_64"

    msbuild = MSBuildToolchain(conanfile)
    assert 'v143' in msbuild.toolset


def test_msbuild_standard():
    settings = Settings({"build_type": ["Release"],
                         "compiler": {"msvc": {"version": ["19.3"], "cppstd": ["20"]}},
                         "os": ["Windows"],
                         "arch": ["x86_64"]})
    conanfile = ConanFile(Mock(), None)
    conanfile.folders.set_base_generators(".")
    conanfile.install_folder = os.getcwd()
    conanfile.conf = ConfDefinition()
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.settings_build = settings
    conanfile.initialize(settings)
    conanfile.settings.build_type = "Release"
    conanfile.settings.compiler = "msvc"
    conanfile.settings.compiler.version = "19.3"
    conanfile.settings.compiler.cppstd = "20"
    conanfile.settings.os = "Windows"
    conanfile.settings.arch = "x86_64"

    msbuild = MSBuildToolchain(conanfile)
    with mock.patch("conan.tools.microsoft.visual.vcvars_path", mock.MagicMock(return_value=".")):
        msbuild.generate()
    assert '<LanguageStandard>stdcpp20</LanguageStandard>' in load('conantoolchain_release_x64.props')
