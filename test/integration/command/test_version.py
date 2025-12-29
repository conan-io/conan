from conan.test.utils.tools import TestClient
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
    assert js["conan_path"] == sys.argv[0]
    assert js["python"]["version"] == _python_version()
    assert js["python"]["sys_version"] == _sys_version()
    assert js["python"]["sys_executable"] == sys.executable
    assert js["python"]["is_frozen"] == getattr(sys, 'frozen', False)
    assert js["python"]["architecture"] == platform.machine()
    assert js["system"]["version"] == platform.version()
    assert js["system"]["platform"] == platform.platform()
    assert js["system"]["system"] == platform.system()
    assert js["system"]["release"] == platform.release()
    assert js["system"]["cpu"] == platform.processor()


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
    assert f'conan_path: {sys.argv[0]}' in lines
    assert 'python' in lines
    assert f'  version: {_python_version()}' in lines
    assert f'  sys_version: {_sys_version()}' in lines
    assert f'  sys_executable: {sys.executable}' in lines
    assert f'  is_frozen: {getattr(sys, "frozen", False)}' in lines
    assert f'  architecture: {platform.machine()}' in lines
    assert 'system' in lines
    assert f'  version: {platform.version()}' in lines
    assert f'  platform: {platform.platform()}' in lines
    assert f'  system: {platform.system()}' in lines
    assert f'  release: {platform.release()}' in lines
    assert f'  cpu: {platform.processor()}' in lines
