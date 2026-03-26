from conan.tools.system import PyEnv
from unittest.mock import patch
import pytest
from conan.api.output import ConanOutput, LEVEL_QUIET, LEVEL_ERROR, LEVEL_WARNING, \
    LEVEL_STATUS, LEVEL_VERBOSE, LEVEL_DEBUG, LEVEL_TRACE
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


@pytest.mark.parametrize("level, expected_pip_flag", [
    (LEVEL_QUIET, "-qqq"),
    (LEVEL_ERROR, "-qq"),
    (LEVEL_WARNING, "-q"),
    (LEVEL_STATUS, None),
    (LEVEL_VERBOSE, "-v"),
    (LEVEL_DEBUG, "-vv"),
    (LEVEL_TRACE, "-vvv"),
])
def test_pyenv_pip_verbosity(level, expected_pip_flag):
    """
    https://github.com/conan-io/conan/issues/19729
    PyEnv.install() should map Conan verbosity levels to pip's native -q/-v flags.
    """
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
        if expected_pip_flag:
            assert f" {expected_pip_flag} " in calls[0]
        else:
            assert " -q" not in calls[0]
            assert " -v " not in calls[0]
    finally:
        ConanOutput.set_output_level(old_level)
