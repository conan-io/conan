from conan.tools.system import PipEnv
from unittest.mock import patch
import mock
import pytest
from unittest.mock import PropertyMock
from conan.errors import ConanException
from conan.internal.model.settings import Settings
from conan.test.utils.mocks import ConanFileMock


@patch('shutil.which')
def test_pipenv_conf(mock_shutil_which):
    # https://github.com/conan-io/conan/issues/11661
    conanfile = ConanFileMock()
    conanfile.settings = Settings()
    mock_shutil_which.side_effect = Exception()
    conanfile.conf.define("tools.system.pipenv:python_interpreter", "/python/interpreter/from/config")
    result = "/python/interpreter/from/config -m venv"
    pipenv = PipEnv(conanfile, "testenv")

    def fake_run(command, win_bash=False, subsystem=None, env=None, ignore_errors=False, quiet=False):
        assert result in command
        return 100
    conanfile.run = fake_run
    pipenv._create_venv()


@patch('shutil.which')
def test_pipenv_error_message(mock_shutil_which):
    # https://github.com/conan-io/conan/issues/11661
    conanfile = ConanFileMock()
    conanfile.settings = Settings()
    mock_shutil_which.return_value = None
    with pytest.raises(ConanException) as exc_info:
        pipenv = PipEnv(conanfile, "testenv")
        pipenv._create_venv()
    assert exc_info.value.args[0] == "PipEnv could not find a Python executable path." \
                                     "Please set 'tools.system.pipenv:python_interpreter' to '</your/python/full/path>' " \
                                     "in the [conf] section of the profile, or in the command line using " \
                                     "'-c tools.system.pipenv:python_interpreter=</your/python/full/path>'"
