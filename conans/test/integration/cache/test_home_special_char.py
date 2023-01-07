import os

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


def test_home_special_chars():
    path_chars = "päthñç$"
    cache_folder = os.path.join(temp_folder(), path_chars)
    current_folder = os.path.join(temp_folder(), path_chars)
    c = TestClient(cache_folder, current_folder)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("install .")
    c.run("create .")
    assert path_chars in c.out
