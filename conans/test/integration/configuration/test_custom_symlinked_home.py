import os
import platform

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() == "Windows", reason="Uses symlinks")
def test_custom_symlinked_home():
    base_cache = temp_folder()
    real_cache = os.path.join(base_cache, "real_cache")
    symlink_cache = os.path.join(base_cache, "symlink_cache")
    os.symlink(symlink_cache, real_cache)
    c = TestClient(cache_folder=symlink_cache)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    assert "symlink_cache" in c.out
    assert "real_cache" not in c.out
