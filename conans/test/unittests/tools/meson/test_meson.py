import textwrap

from conan.tools.meson import Meson
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import ConanFileMock, MockSettings


def test_meson_build():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.ninja:jobs=23
        tools.build:processes=10
    """))

    settings = MockSettings({"build_type": "Release",
                             "compiler": "gcc",
                             "compiler.version": "7",
                             "os": "Linux",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.display_name = 'test'
    conanfile.conf = c.get_conanfile_conf(None)

    meson = Meson(conanfile)
    meson.build()
    
    assert '-j23' in str(conanfile.command)
