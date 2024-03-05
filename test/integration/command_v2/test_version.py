from conans.test.utils.tools import TestClient
from conan import __version__
import json
import platform
import sys


def _python_version():
    return platform.python_version().replace("\n", "")


def _sys_version():
    return sys.version.replace("\n", "")


def test_version_json():
    """
    Conan version command should be able to output a json with the version and python version.
    """
    t = TestClient()
    t.run("version --format=json")
    js = json.loads(t.stdout)
    assert js["version"] == __version__
    assert js["python"]["version"] == _python_version()
    assert js["python"]["sys_version"] == _sys_version()


def test_version_text():
    """
    Conan version command should be able to output a raw text with the version and python version.
    """
    t = TestClient()
    t.run("version --format=text")
    _validate_text_output(t.out)


def test_version_raw():
    """
    Conan version command should be able to output a raw text with the version and python version,
    when no format is specified.
    """
    t = TestClient()
    t.run("version")
    _validate_text_output(t.out)


def _validate_text_output(output):
    lines = output.splitlines()
    assert f'version: {__version__}' in lines
    assert 'python' in lines
    assert f'  version: {_python_version()}' in lines
    assert f'  sys_version: {_sys_version()}' in lines
