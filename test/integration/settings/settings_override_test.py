import os

import pytest

from conans.model.recipe_ref import RecipeReference
from conan.internal.paths import CONANINFO
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import load


@pytest.fixture()
def client():
    client = TestClient()
    conanfile = GenConanfile("mingw", "0.1").with_settings("compiler")
    build_msg = """
    def build(self):
        self.output.warning("COMPILER=> %s %s" % (self.name, str(self.settings.compiler)))
    """
    client.save({"conanfile.py": str(conanfile) + build_msg})
    client.run("export . --user=lasote --channel=testing")
    conanfile = GenConanfile("visual", "0.1").with_requires("mingw/0.1@lasote/testing")
    conanfile.with_settings("compiler")
    client.save({"conanfile.py": str(conanfile) + build_msg})
    client.run("export . --user=lasote --channel=testing")
    return client


def test_override(client):
    client.run("install --requires=visual/0.1@lasote/testing --build missing -s compiler=msvc "
               "-s compiler.version=191 -s compiler.runtime=dynamic "
               "-s mingw*:compiler='gcc' -s mingw*:compiler.libcxx='libstdc++' "
               "-s mingw*:compiler.version=4.8")

    assert "COMPILER=> mingw gcc" in client.out
    assert "COMPILER=> visual msvc" in client.out

    # CHECK CONANINFO FILE
    latest_rrev = client.cache.get_latest_recipe_reference(
        RecipeReference.loads("mingw/0.1@lasote/testing"))
    pkg_ids = client.cache.get_package_references(latest_rrev)
    latest_prev = client.cache.get_latest_package_reference(pkg_ids[0])
    package_path = client.cache.pkg_layout(latest_prev).package()
    conaninfo = load(os.path.join(package_path, CONANINFO))
    assert "compiler=gcc" in conaninfo

    # CHECK CONANINFO FILE
    package_path = client.created_layout().package()
    conaninfo = load(os.path.join(package_path, CONANINFO))
    assert "compiler=msvc" in conaninfo
    assert "compiler.version=191" in conaninfo


def test_non_existing_setting(client):
    client.run("install --requires=visual/0.1@lasote/testing --build missing -s compiler=msvc "
               "-s compiler.version=191 -s compiler.runtime=dynamic "
               "-s mingw/*:missingsetting='gcc' ", assert_error=True)
    assert "settings.missingsetting' doesn't exist" in client.out


def test_override_in_non_existing_recipe(client):
    client.run("install --requires=visual/0.1@lasote/testing --build missing -s compiler=msvc "
               "-s compiler.version=191 -s compiler.runtime=dynamic "
               "-s MISSINGID:compiler='gcc' ")

    assert "COMPILER=> mingw msvc" in client.out
    assert "COMPILER=> visual msvc" in client.out


def test_exclude_patterns_settings():

    client = TestClient()
    gen = GenConanfile().with_settings("build_type")
    client.save({"zlib/conanfile.py": gen})
    client.save({"openssl/conanfile.py": gen.with_require("zlib/1.0")})
    client.save({"consumer/conanfile.py": gen.with_require("openssl/1.0")})
    client.run("create zlib --name zlib --version 1.0")
    client.run("create openssl --name openssl --version 1.0")

    # We miss openssl and zlib debug packages
    client.run("install consumer -s build_type=Debug", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'openssl/1.0', 'zlib/1.0'" in client.out

    # All except zlib are Release, the only missing is zlib debug
    client.run("install consumer -s build_type=Debug "
               "                 -s !zlib*:build_type=Release", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'zlib/1.0'"

    # All the packages matches !potato* so all are Release
    client.run("install consumer -s build_type=Debug -s !potato*:build_type=Release")

    # All the packages except the consumer are Release, but we are creating consumer in Debug
    client.run("create consumer --name=consumer --version=1.0 "
               "-s=build_type=Debug -s=!&:build_type=Release")

    client.run("install --requires consumer/1.0 -s consumer/*:build_type=Debug")

    # Priority between package scoped settings
    client.run('remove consumer/*#* -c')
    client.run("install --reference consumer/1.0 -s build_type=Debug", assert_error=True)
    # Pre-check, there is no Debug package for any of them
    assert "ERROR: Missing prebuilt package for 'consumer/1.0', 'openssl/1.0', 'zlib/1.0'"
    # Pre-check there are Release packages
    client.run("create consumer --name=consumer --version=1.0 -s build_type=Release")

    # Try to install with this two scoped conditions, This is OK the right side has priority
    client.run("install --requires consumer/1.0 -s zlib/*:build_type=Debug -s *:build_type=Release")

    # Try to install with this two scoped conditions, This is ERROR the right side has priority
    client.run("install --requires consumer/1.0 -s *:build_type=Release -s zlib/*:build_type=Debug",
               assert_error=True)
    assert "ERROR: Missing prebuilt package for 'zlib/1.0'" in client.out

    # Try to install with this two scoped conditions, This is OK again, the right side has priority
    # The z* points to Release later, so zlib in Release
    client.run("install --requires consumer/1.0 -s *:build_type=Release "
               "-s zlib/*:build_type=Debug -s z*:build_type=Release")

    # Try to install with this two scoped conditions, This is OK again, the right side has priority
    # No package is potato, so all packages in Release
    client.run("install --requires consumer/1.0 -s !zlib:build_type=Debug "
               "-s !potato:build_type=Release")

