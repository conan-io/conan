import textwrap

import pytest

from conan.tools.microsoft import unix_path, unix_path_package_info_legacy
from conans.model.conf import ConfDefinition
from conan.test.utils.mocks import MockSettings, ConanFileMock

expected_results = [
    ("msys2", '/c/path/to/stuff'),
    ("msys", '/c/path/to/stuff'),
    ("cygwin", '/cygdrive/c/path/to/stuff'),
    ("wsl", '/mnt/c/path/to/stuff'),
]


@pytest.mark.parametrize("subsystem, expected_path", expected_results)
def test_unix_path(subsystem, expected_path):
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.microsoft.bash:subsystem={}
        tools.microsoft.bash:active=True
    """.format(subsystem)))

    settings = MockSettings({"os": "Windows"})
    conanfile = ConanFileMock()
    conanfile.conf = c.get_conanfile_conf(None)
    conanfile.settings = settings
    conanfile.settings_build = settings

    test_path = "c:/path/to/stuff"
    path = unix_path(conanfile, test_path)
    assert expected_path == path

    package_info_legacy_path = unix_path_package_info_legacy(conanfile, test_path, path_flavor=subsystem)
    assert package_info_legacy_path == test_path
