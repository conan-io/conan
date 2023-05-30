from conans.test.utils.tools import TestClient
from conan import __version__
import json
import platform
import sys


def test_version_json():
    t = TestClient()
    t.run("version --format=json")
    js = json.loads(t.stdout)
    assert js["version"] == __version__
    assert js["python"]["version"] == platform.python_version()
    assert js["python"]["sys_version"] == sys.version


def test_version_text():
    t = TestClient()
    t.run("version --format=text")
    assert [f'version: {__version__}', f'python.version: {platform.python_version()}', f'python.sys_version: {sys.version}'] == t.out.splitlines()


def test_version_raw():
    t = TestClient()
    t.run("version")
    assert [f'version: {__version__}', f'python.version: {platform.python_version()}', f'python.sys_version: {sys.version}'] == t.out.splitlines()
