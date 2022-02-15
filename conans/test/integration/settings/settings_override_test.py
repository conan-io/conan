import os

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.paths import CONANINFO
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
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
    client.run("install --reference=visual/0.1@lasote/testing --build missing -s compiler='Visual Studio' "
               "-s compiler.version=14 -s compiler.runtime=MD "
               "-s mingw*:compiler='gcc' -s mingw*:compiler.libcxx='libstdc++' "
               "-s mingw*:compiler.version=4.8")

    assert "COMPILER=> mingw gcc" in client.out
    assert "COMPILER=> visual Visual Studio" in client.out

    # CHECK CONANINFO FILE
    latest_rrev = client.cache.get_latest_recipe_reference(
        RecipeReference.loads("mingw/0.1@lasote/testing"))
    pkg_ids = client.cache.get_package_references(latest_rrev)
    latest_prev = client.cache.get_latest_package_reference(pkg_ids[0])
    package_path = client.cache.pkg_layout(latest_prev).package()
    conaninfo = load(os.path.join(package_path, CONANINFO))
    assert "compiler=gcc" in conaninfo

    # CHECK CONANINFO FILE
    latest_rrev = client.cache.get_latest_recipe_reference(
        RecipeReference.loads("visual/0.1@lasote/testing"))
    pkg_ids = client.cache.get_package_references(latest_rrev)
    latest_prev = client.cache.get_latest_package_reference(pkg_ids[0])
    package_path = client.cache.pkg_layout(latest_prev).package()
    conaninfo = load(os.path.join(package_path, CONANINFO))
    assert "compiler=Visual Studio" in conaninfo
    assert "compiler.version=14" in conaninfo


def test_non_existing_setting(client):
    client.run("install --reference=visual/0.1@lasote/testing --build missing -s compiler='Visual Studio' "
               "-s compiler.version=14 -s compiler.runtime=MD "
               "-s mingw/*:missingsetting='gcc' ", assert_error=True)
    assert "settings.missingsetting' doesn't exist" in client.out


def test_override_in_non_existing_recipe(client):
    client.run("install --reference=visual/0.1@lasote/testing --build missing -s compiler='Visual Studio' "
               "-s compiler.version=14 -s compiler.runtime=MD "
               "-s MISSINGID:compiler='gcc' ")

    assert "COMPILER=> mingw Visual Studio" in client.out
    assert "COMPILER=> visual Visual Studio" in client.out
