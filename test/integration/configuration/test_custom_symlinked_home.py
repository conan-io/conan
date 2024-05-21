import os
import platform

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


@pytest.mark.skipif(platform.system() == "Windows", reason="Uses symlinks")
def test_custom_symlinked_home():
    base_cache = temp_folder()
    real_cache = os.path.join(base_cache, "real_cache")
    os.makedirs(real_cache)
    symlink_cache = os.path.join(base_cache, "symlink_cache")
    os.symlink(real_cache, symlink_cache)
    c = TestClient(cache_folder=symlink_cache)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    assert "symlink_cache" in c.out
    assert "real_cache" not in c.out
    c.run("cache path pkg/0.1")
    assert "symlink_cache" in c.out
    assert "real_cache" not in c.out
    c.run(f"cache path pkg/0.1:{NO_SETTINGS_PACKAGE_ID}")
    assert "symlink_cache" in c.out
    assert "real_cache" not in c.out
