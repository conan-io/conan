import os
import shutil

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_cache_path():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile().with_settings("os")})
    c.run("create . --name=pkg --version=1.0 -s os=Linux")
    c.run("create . --name=pkg --version=1.1 -s os=Linux")
    c.run("create . --name=other --version=2.0 -s os=Linux")
    c.run("cache get pkg/*:*")
    print(c.out)
    print(c.current_folder)
    cache_path = os.path.join(c.current_folder, "cache.tgz")
    assert os.path.exists(cache_path)

    c2 = TestClient()
    # Create a package in the cache to check put doesn't interact badly
    c2.save({"conanfile.py": GenConanfile().with_settings("os")})
    c2.run("create . --name=pkg2 --version=3.0 -s os=Windows")
    shutil.copy2(cache_path, c2.current_folder)
    c2.run("cache put cache.tgz")
    print(c2.out)
    print(c2.cache_folder)
    c2.run("list *:*#*")
    print(c2.out)
    assert "pkg2/3.0" in c2.out
    assert "pkg/1.0" in c2.out
    assert "pkg/1.1" in c2.out
    assert "other/2.0" not in c2.out
