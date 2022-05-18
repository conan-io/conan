import json
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_basic_inspect():
    t = TestClient()
    t.save({"foo/conanfile.py": GenConanfile().with_name("foo").with_shared_option()})
    t.run("inspect path foo/conanfile.py")
    lines = t.out.splitlines()
    assert lines == ["default_options:",
                     "    shared: False",
                     'generators: []',
                     'name: foo',
                     "options:",
                     "    shared: [True, False]",
                     'revision_mode: hash',
                     ]


def test_options_description():
    t = TestClient()
    conanfile = textwrap.dedent("""\
        from conan import ConanFile
        class Pkg(ConanFile):
            options = {"shared": [True, False, None], "fpic": [True, False, None]}
            options_description = {"shared": "Some long explanation about shared option",
                                   "fpic": "Yet another long explanation of fpic"}
            """)
    t.save({"foo/conanfile.py": conanfile})
    t.run("inspect path foo/conanfile.py")
    assert "shared: Some long explanation about shared option" in t.out
    assert "fpic: Yet another long explanation of fpic" in t.out


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
