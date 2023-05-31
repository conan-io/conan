from conans.test.utils.tools import TestClient
from conan import __version__
import json
import platform
import sys


def test_version_json():
    """
    Conan version command should be able to output a json with the version and python version.
    """
    t = TestClient()
    t.run("version --format=json")
    js = json.loads(t.stdout)
    assert js["version"] == __version__
    assert js["python"]["version"] == platform.python_version()
    assert js["python"]["sys_version"] == sys.version


def _validate_text_output(output):
    lines = output.splitlines()
    python_version = platform.python_version().replace("\n", "")
    sys_version = sys.version.replace("\n", "")
    assert f'version: {__version__}' in lines
    assert 'python' in lines
    assert f'  version: {python_version}' in lines
    assert f'  sys_version: {sys_version}' in lines


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
