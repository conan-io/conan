import json
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_basic_inspect():
    t = TestClient()
    t.save({"foo/conanfile.py": GenConanfile().with_name("foo").with_shared_option()})
    t.run("inspect foo/conanfile.py")
    lines = t.out.splitlines()
    assert lines == ["default_options:",
                     "    shared: False",

                     'generators: []',
                     'name: foo',
                     'no_copy_source: False',
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
    t.run("inspect foo/conanfile.py")
    assert "shared: Some long explanation about shared option" in t.out
    assert "fpic: Yet another long explanation of fpic" in t.out


def test_missing_conanfile():
    t = TestClient()
    t.run("inspect missing/conanfile.py", assert_error=True)
    assert "Conanfile not found at" in t.out


def test_dot_and_folder_conanfile():
    t = TestClient()
    t.save({"conanfile.py": GenConanfile().with_name("foo")})
    t.run("inspect .")
    assert 'name: foo' in t.out
    t.save({"foo/conanfile.py": GenConanfile().with_name("foo")}, clean_first=True)
    t.run("inspect foo")
    assert 'name: foo' in t.out
