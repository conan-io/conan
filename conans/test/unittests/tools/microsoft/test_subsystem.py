import mock
import textwrap
import pytest

from conan.tools.microsoft import unix_path, unix_path_package_info_legacy
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import MockSettings, ConanFileMock

expected_results = [
    ("msys2", '/c/path/to/stuff'),
    ("msys", '/c/path/to/stuff'),
    ("cygwin", '/cygdrive/c/path/to/stuff'),
    ("wsl", '/mnt/c/path/to/stuff'),
    ("sfu", '/dev/fs/C/path/to/stuff')
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

    path = unix_path(conanfile, "c:/path/to/stuff")
    assert expected_path == path

@mock.patch("platform.system", mock.MagicMock(return_value='Windows'))
@pytest.mark.parametrize("subsystem, expected_path", expected_results)
def test_unix_path_package_info_legacy_windows(subsystem, expected_path):
    test_path = "c:/path/to/stuff"
    conanfile = ConanFileMock()
    package_info_legacy_path = unix_path_package_info_legacy(conanfile, test_path, path_flavor=subsystem)
    assert expected_path == package_info_legacy_path

@mock.patch("platform.system", mock.MagicMock(return_value='Darwin'))
@pytest.mark.parametrize("subsystem, expected_path", expected_results)
def test_unix_path_package_info_legacy_not_windows(subsystem, expected_path):
    test_path = "c:/path/to/stuff"
    conanfile = ConanFileMock()
    package_info_legacy_path = unix_path_package_info_legacy(conanfile, test_path, path_flavor=subsystem)
    assert test_path == package_info_legacy_path