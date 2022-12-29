import os

import pytest

from conans.client import tools
from conans.model.ref import ConanFileReference
from conans.paths import CONANINFO
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import load


@pytest.fixture()
def client():
    client = TestClient()
    conanfile = GenConanfile("MinGWBuild", "0.1").with_settings("compiler")
    build_msg = """
    def build(self):
        self.output.warn("COMPILER=> %s %s" % (self.name, str(self.settings.compiler)))
    """
    client.save({"conanfile.py": str(conanfile) + build_msg})
    client.run("export . lasote/testing")
    conanfile = GenConanfile("VisualBuild", "0.1").with_requires("MinGWBuild/0.1@lasote/testing")
    conanfile.with_settings("compiler")
    client.save({"conanfile.py": str(conanfile) + build_msg})
    client.run("export . lasote/testing")
    return client


def test_override(client):
    client.run("install VisualBuild/0.1@lasote/testing --build missing -s compiler='Visual Studio' "
               "-s compiler.version=14 -s compiler.runtime=MD "
               "-s MinGWBuild:compiler='gcc' -s MinGWBuild:compiler.libcxx='libstdc++' "
               "-s MinGWBuild:compiler.version=4.8")

    assert "COMPILER=> MinGWBuild gcc" in client.out
    assert "COMPILER=> VisualBuild Visual Studio" in client.out

    # CHECK CONANINFO FILE
    packs_dir = client.cache.package_layout(
        ConanFileReference.loads("MinGWBuild/0.1@lasote/testing")).packages()
    pack_dir = os.path.join(packs_dir, os.listdir(packs_dir)[0])
    conaninfo = load(os.path.join(pack_dir, CONANINFO))
    assert "compiler=gcc" in conaninfo

    # CHECK CONANINFO FILE
    packs_dir = client.cache.package_layout(
        ConanFileReference.loads("VisualBuild/0.1@lasote/testing")).packages()
    pack_dir = os.path.join(packs_dir, os.listdir(packs_dir)[0])
    conaninfo = load(os.path.join(pack_dir, CONANINFO))
    assert "compiler=Visual Studio" in conaninfo
    assert "compiler.version=14" in conaninfo


def test_non_existing_setting(client):
    client.run("install VisualBuild/0.1@lasote/testing --build missing -s compiler='Visual Studio' "
               "-s compiler.version=14 -s compiler.runtime=MD "
               "-s MinGWBuild:missingsetting='gcc' ", assert_error=True)
    assert "settings.missingsetting' doesn't exist" in client.out


def test_override_in_non_existing_recipe(client):
    client.run("install VisualBuild/0.1@lasote/testing --build missing -s compiler='Visual Studio' "
               "-s compiler.version=14 -s compiler.runtime=MD "
               "-s MISSINGID:compiler='gcc' ")

    assert "COMPILER=> MinGWBuild Visual Studio" in client.out
    assert "COMPILER=> VisualBuild Visual Studio" in client.out


def test_override_setting_with_env_variables(client):
    with tools.environment_append({"CONAN_ENV_COMPILER": "Visual Studio",
                                   "CONAN_ENV_COMPILER_VERSION": "14",
                                   "CONAN_ENV_COMPILER_RUNTIME": "MD"}):
        client.run("install VisualBuild/0.1@lasote/testing --build missing")

    assert "COMPILER=> MinGWBuild Visual Studio" in client.out
