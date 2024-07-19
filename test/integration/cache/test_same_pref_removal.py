import os

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_same_pref_removal():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("export .")
    c.run("install --requires=pkg/0.1 --build=pkg*")
    layout = c.created_layout()
    pkg_folder1 = layout.package()
    assert os.path.exists(os.path.join(pkg_folder1, "conanmanifest.txt"))
    assert os.path.exists(os.path.join(pkg_folder1, "conaninfo.txt"))
    c.run("install --requires=pkg/0.1 --build=pkg*")
    layout = c.created_layout()
    pkg_folder2 = layout.package()
    assert pkg_folder1 == pkg_folder2
    assert os.path.exists(os.path.join(pkg_folder1, "conanmanifest.txt"))
    assert os.path.exists(os.path.join(pkg_folder1, "conaninfo.txt"))
