import textwrap

from conan.tools.microsoft import MSBuild
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import ConanFileMock, MockSettings


def test_meson_build():
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
