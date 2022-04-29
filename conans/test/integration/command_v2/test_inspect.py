import json

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_basic_inspect():
    t = TestClient()
    t.save({"foo/conanfile.py": GenConanfile().with_name("foo").with_shared_option()})
    t.run("inspect foo/conanfile.py name options")
    lines = t.out.splitlines()
    assert lines == ["name: foo", "options: {'shared': [True, False]}"]


def test_missing_conanfile():
    t = TestClient()
    t.run("inspect missing/conanfile.py name", assert_error=True)
    assert "conanfile.py not found!" in t.out


def test_missing_attribute():
    t = TestClient()
    t.save({"foo/conanfile.py": GenConanfile().with_name("foo").with_shared_option()})
    t.run("inspect foo/conanfile.py missing", assert_error=True)
    assert "The conanfile doesn't have a 'missing' attribute" in t.out


def test_json():
    t = TestClient()
    t.save({"foo/conanfile.py": GenConanfile().with_name("foo").with_shared_option()})
    t.run("inspect foo/conanfile.py name options --format json")
    assert json.loads(t.stdout) == {"attributes": {"name": "foo",
                                                   "options": {"shared": [True, False]}}}

