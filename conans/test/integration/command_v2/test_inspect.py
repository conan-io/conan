import json

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_basic_inspect():
    t = TestClient()
    t.save({"foo/conanfile.py": GenConanfile().with_name("foo").with_shared_option()})
    t.run("inspect path foo/conanfile.py")
    lines = t.out.splitlines()
    assert lines == ['author: None',
                     'build_policy: None',
                     'build_requires: None',
                     'channel: None',
                     "default_options: {'shared': False}",
                     'deprecated: None',
                     'description: None',
                     'exports: None',
                     'exports_sources: None',
                     'generators: []',
                     'homepage: None',
                     'license: None',
                     'name: foo',
                     "options: {'shared': [True, False]}",
                     'package_type: None',
                     'provides: None',
                     'requires: None',
                     'revision_mode: hash',
                     'settings: None',
                     'test_requires: None',
                     'tested_reference_str: None',
                     'tool_requires: None',
                     'topics: None',
                     'url: None',
                     'user: None',
                     'version: None',
                     'win_bash: None']


def test_missing_conanfile():
    t = TestClient()
    t.run("inspect path missing/conanfile.py", assert_error=True)
    assert "conanfile.py not found!" in t.out


def test_json():
    t = TestClient()
    t.save({"foo/conanfile.py": GenConanfile().with_name("foo").with_shared_option()})
    t.run("inspect path foo/conanfile.py --format json")
    assert json.loads(t.stdout)["name"] == "foo"
    assert json.loads(t.stdout)["options"] == {"shared": [True, False]}

