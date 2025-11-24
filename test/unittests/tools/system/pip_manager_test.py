from conan.tools.system import PipEnv
from unittest.mock import patch
import pytest
from conan.errors import ConanException
from conan.internal.model.settings import Settings
from conan.test.utils.mocks import ConanFileMock


@patch('shutil.which')
def test_pipenv_conf(mock_shutil_which):
    conanfile = ConanFileMock()
    conanfile.settings = Settings()
    conanfile.conf.define("tools.system.pipenv:python_interpreter",
                          "/python/interpreter/from/config")
    result = "/python/interpreter/from/config -m venv"
    PipEnv(conanfile, "testenv")

    def fake_run(command, win_bash=False, subsystem=None, env=None, ignore_errors=False,   # noqa
                 quiet=False):  # noqa
        assert result in command
        return 100
    conanfile.run = fake_run
    mock_shutil_which.assert_not_called()


@patch('shutil.which')
def test_pipenv_error_message(mock_shutil_which):
    conanfile = ConanFileMock()
    conanfile.settings = Settings()
    mock_shutil_which.return_value = None
    with pytest.raises(ConanException) as exc_info:
        PipEnv(conanfile, "testenv")
    assert ("install Python system-wide or set the 'tools.system.pipenv:python_interpreter' "
            "conf") in exc_info.value.args[0]


def test_pipenv_creation_error_message():
    conanfile = ConanFileMock()
    conanfile.settings = Settings()
    conanfile.conf.define("tools.system.pipenv:python_interpreter",
                          "/python/interpreter/from/config")

    def fake_run(command, win_bash=False, subsystem=None, env=None, ignore_errors=False,   # noqa
                 quiet=False):  # noqa
        raise ConanException("fake error message")
    conanfile.run = fake_run
    with pytest.raises(ConanException) as exc_info:
        PipEnv(conanfile, "testenv")
    assert "using '/python/interpreter/from/config': fake error message" in exc_info.value.args[0]
