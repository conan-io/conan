import os

import pytest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.fixture
def conanfile():
    conanfile = str(GenConanfile().with_import("from conans import tools")
                    .with_import("import os")
                    .with_settings("build_type")
                    .with_import("from conan.tools.layout import clion_layout"))

    conanfile += """
    def source(self):
        tools.save("include/myheader.h", "")

    def build(self):
        tools.save("mylib.lib", "")

    def shape(self):
        clion_layout(self)
    """
    return conanfile


def test_clion_layout_in_cache(conanfile):
    """The layout in the cache is used too, always relative to the "base" folders that the cache
    requires. But by the default, the "package" is not followed
    """
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    ref = ConanFileReference.loads("lib/1.0@")
    pref_release = PackageReference(ref, "4024617540c4f240a6a5e8911b0de9ef38a11a72")
    bf_release = client.cache.package_layout(ref).build(pref_release)
    pf_release = client.cache.package_layout(ref).package(pref_release)
    pref_debug = PackageReference(ref, "5a67a79dbc25fd0fa149a0eb7a20715189a0d988")
    bf_debug = client.cache.package_layout(ref).build(pref_debug)
    pf_debug = client.cache.package_layout(ref).package(pref_debug)
    build_folder_release = os.path.join(bf_release, "cmake-build-release")
    build_folder_debug = os.path.join(bf_debug, "cmake-build-debug")

    client.run("create . lib/1.0@")
    # Check the build folder (release)
    assert os.path.exists(os.path.join(build_folder_release, "mylib.lib"))

    # Check the package folder (release)
    assert os.path.exists(os.path.join(pf_release, "lib/mylib.lib"))
    assert os.path.exists(os.path.join(pf_release, "include/myheader.h"))

    client.run("create . lib/1.0@ -s build_type=Debug")
    # Check the build folder (debug)
    assert os.path.exists(os.path.join(build_folder_debug, "mylib.lib"))

    # Check the package folder (debug)
    assert os.path.exists(os.path.join(pf_debug, "lib/mylib.lib"))
    assert os.path.exists(os.path.join(pf_debug, "include/myheader.h"))


def test_clion_layout_with_local_methods(conanfile):
    """The layout in the cache is used too, always relative to the "base" folders that the cache
        requires. But by the default, the "package" is not followed
        """
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("install . lib/1.0@")
    client.run("source .")
    # Check the source folder (release)
    assert os.path.exists(os.path.join(client.current_folder, "include", "myheader.h"))
    client.run("build .")
    # Check the build folder (release)
    assert os.path.exists(os.path.join(client.current_folder, "cmake-build-release", "mylib.lib"))

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("install . lib/1.0@ -s build_type=Debug")
    client.run("source .")
    # Check the source folder (release)
    assert os.path.exists(os.path.join(client.current_folder, "include", "myheader.h"))
    client.run("build .")
    # Check the build folder (release)
    assert os.path.exists(os.path.join(client.current_folder, "cmake-build-debug", "mylib.lib"))


