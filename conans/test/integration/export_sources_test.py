import os
import textwrap

from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_exports():
    """ Check that exported files go to the right folder
    """
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"
            exports = "*.h"
        """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "hello.h": "hello",
            "data.txt": "data"})
    c.run("create .")
    ref = RecipeReference.loads("hello/0.1")
    ref_layout = c.get_latest_ref_layout(ref)

    def assert_files(folder, files):
        assert sorted(os.listdir(folder)) == sorted(files)

    assert_files(ref_layout.source(), [])
    assert_files(ref_layout.export(), ['conanfile.py', 'conanmanifest.txt', 'hello.h'])
    assert_files(ref_layout.export_sources(), [])


def test_exports_sources():
    """ Check that exported-sources files go to the right folder AND to the source folder
        """
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"
            exports_sources = "*.h"
        """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "hello.h": "hello",
            "data.txt": "data"})
    c.run("create .")
    ref = RecipeReference.loads("hello/0.1")
    ref_layout = c.get_latest_ref_layout(ref)

    def assert_files(folder, files):
        assert sorted(os.listdir(folder)) == sorted(files)

    assert_files(ref_layout.source(), ['hello.h'])
    assert_files(ref_layout.export(), ['conanfile.py', 'conanmanifest.txt', ])
    assert_files(ref_layout.export_sources(), ['hello.h'])


def test_test_package_copied():
    """The exclusion of the test_package folder have been removed so now we test that indeed is
    exported"""

    client = TestClient()
    conanfile = GenConanfile().with_exports("*").with_exports_sources("*")
    client.save({"conanfile.py": conanfile,
                 "test_package/foo.txt": "bar"})
    client.run("export . --name foo --version 1.0")
    assert "Copied 2 '.txt' file" in client.out
