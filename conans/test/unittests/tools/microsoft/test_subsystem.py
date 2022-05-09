import textwrap

import pytest

from conan.tools.microsoft import unix_path
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import MockSettings, ConanFileMock


@pytest.mark.parametrize("subsystem, expected_path", [
    ("msys2", '/c/path/to/stuff'),
    ("msys", '/c/path/to/stuff'),
    ("cygwin", '/cygdrive/c/path/to/stuff'),
    ("wsl", '/mnt/c/path/to/stuff'),
    ("sfu", '/dev/fs/C/path/to/stuff')
])
def test_unix_path(subsystem, expected_path):
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.microsoft.bash:subsystem={}
    """.format(subsystem)))

    settings = MockSettings({"os": "Windows"})
    conanfile = ConanFileMock()
    conanfile.conf = c.get_conanfile_conf(None)
    conanfile.settings = settings
    conanfile.settings_build = settings
    conanfile.win_bash = True

    path = unix_path(conanfile, "c:/path/to/stuff")
    assert expected_path == path
