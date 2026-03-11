from conan.tools.system import PyEnv
from unittest.mock import patch
import pytest
from conan.api.output import ConanOutput, LEVEL_ERROR, LEVEL_STATUS, LEVEL_WARNING, LEVEL_VERBOSE
from conan.errors import ConanException
from conan.internal.model.settings import Settings
from conan.test.utils.mocks import ConanFileMock


@patch('shutil.which')
def test_pyenv_conf(mock_shutil_which):
    conanfile = ConanFileMock()
    conanfile.settings = Settings()
    conanfile.conf.define("tools.system.pyenv:python_interpreter",
                          "/python/interpreter/from/config")

    def fake_run(command, win_bash=False, subsystem=None, env=None, ignore_errors=False,  # noqa
                 quiet=False):  # noqa
        assert "/python/interpreter/from/config" in command

    conanfile.run = fake_run
    PyEnv(conanfile, "testenv")
    mock_shutil_which.assert_not_called()


@patch('shutil.which')
def test_pyenv_deprecated_conf(mock_shutil_which):
    conanfile = ConanFileMock()
    conanfile.settings = Settings()
    conanfile.conf.define("tools.system.pipenv:python_interpreter",
                          "/python/interpreter/from/config")

    def fake_run(command, win_bash=False, subsystem=None, env=None, ignore_errors=False,  # noqa
                 quiet=False):  # noqa
        assert "/python/interpreter/from/config" in command

    conanfile.run = fake_run
    PyEnv(conanfile, "testenv")
    mock_shutil_which.assert_not_called()


@patch('shutil.which')
def test_pyenv_error_message(mock_shutil_which):
    conanfile = ConanFileMock()
    conanfile.settings = Settings()
    mock_shutil_which.return_value = None
    with pytest.raises(ConanException) as exc_info:
        PyEnv(conanfile, "testenv")
    assert ("install Python system-wide or set the 'tools.system.pyenv:python_interpreter' "
            "conf") in exc_info.value.args[0]


def test_pyenv_creation_error_message():
    conanfile = ConanFileMock()
    conanfile.settings = Settings()
    conanfile.conf.define("tools.system.pyenv:python_interpreter",
                          "/python/interpreter/from/config")

    def fake_run(command, win_bash=False, subsystem=None, env=None, ignore_errors=False,   # noqa
                 quiet=False):  # noqa
        raise ConanException("fake error message")
    conanfile.run = fake_run
    with pytest.raises(ConanException) as exc_info:
        PyEnv(conanfile, "testenv")
    assert "using '/python/interpreter/from/config': fake error message" in exc_info.value.args[0]


@pytest.mark.parametrize("level, expected_quiet", [
    (LEVEL_ERROR, True),
    (LEVEL_WARNING, True),
    (LEVEL_STATUS, False),
    (LEVEL_VERBOSE, False),
])
def test_pyenv_quiet_with_high_verbosity(level, expected_quiet):
    conanfile = ConanFileMock()
    conanfile.settings = Settings()
    conanfile.conf.define("tools.system.pyenv:python_interpreter",
                          "/python/interpreter/from/config")

    calls = []

    def fake_run(command, win_bash=False, subsystem=None, env=None, ignore_errors=False,  # noqa
                 quiet=False):  # noqa
        calls.append(command)

    conanfile.run = fake_run

    old_level = ConanOutput.get_output_level()
    try:
        ConanOutput.set_output_level(level)
        pyenv = PyEnv(conanfile, f"testenv_{level}")
        calls.clear()

        pyenv.install(["some_package"])
        assert len(calls) == 1
        assert "pip install" in calls[0]
        if expected_quiet:
            assert " -q " in calls[0]
        else:
            assert " -q " not in calls[0]
    finally:
        ConanOutput.set_output_level(old_level)
