import os
import platform
import textwrap

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TurboTestClient
from conans.util.files import load, rmdir


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
    assert "Copied 1 '.txt' file" in client.out


@pytest.mark.skipif(platform.system() == "Windows", reason="Symlinks not in Windows")
def test_exports_does_not_follow_symlink():
    def absolute_existing_folder():
        tmp = temp_folder()
        with open(os.path.join(tmp, "source.cpp"), "a") as _f:
            _f.write("foo")
        return tmp

    linked_abs_folder = absolute_existing_folder()
    client = TurboTestClient(default_server_user=True)
    conanfile = GenConanfile()\
        .with_package('copy(self, "*", self.source_folder, self.package_folder)')\
        .with_exports_sources("*")\
        .with_import("from conan.tools.files import copy")
    client.save({"conanfile.py": conanfile, "foo.txt": "bar"})
    os.symlink(linked_abs_folder, os.path.join(client.current_folder, "linked_folder"))
    pref = client.create(RecipeReference.loads("lib/1.0"), conanfile=False)
    exports_sources_folder = client.get_latest_ref_layout(pref.ref).export_sources()
    assert os.path.islink(os.path.join(exports_sources_folder, "linked_folder"))
    assert os.path.exists(os.path.join(exports_sources_folder, "linked_folder", "source.cpp"))

    # Check files have been copied to the build
    build_folder = client.get_latest_pkg_layout(pref).build()
    assert os.path.islink(os.path.join(build_folder, "linked_folder"))
    assert os.path.exists(os.path.join(build_folder, "linked_folder", "source.cpp"))

    # Check package files are there
    package_folder = client.get_latest_pkg_layout(pref).package()
    assert os.path.islink(os.path.join(package_folder, "linked_folder"))
    assert os.path.exists(os.path.join(package_folder, "linked_folder", "source.cpp"))

    # Check that the manifest doesn't contain the symlink nor the source.cpp
    contents = load(os.path.join(package_folder, "conanmanifest.txt"))
    assert "foo.txt" in contents
    assert "linked_folder" not in contents
    assert "source.cpp" not in contents

    # Now is a broken link, but the files are not in the cache, just a broken link
    rmdir(linked_abs_folder)
    assert not os.path.exists(os.path.join(exports_sources_folder, "linked_folder", "source.cpp"))
    assert not os.path.exists(os.path.join(build_folder, "linked_folder", "source.cpp"))
    assert not os.path.exists(os.path.join(package_folder, "linked_folder", "source.cpp"))
