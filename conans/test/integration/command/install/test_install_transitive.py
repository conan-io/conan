import os

import pytest

from conans.model.info import ConanInfo, load_binary_info
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.paths import CONANFILE_TXT, CONANINFO
from conans.test.utils.tools import TestClient,  GenConanfile
from conans.util.files import save, load


@pytest.fixture()
def client():
    c = TestClient()
    save(c.cache.settings_path, "os: [Windows, Macos, Linux, FreeBSD]\nos_build: [Windows, Macos]\narch_build: [x86_64]")
    save(c.cache.default_profile_path, "[settings]\nos=Windows")

    def base_conanfile(name):
        return GenConanfile(name, "0.1").with_option("language", [0, 1])\
            .with_default_option("language", 0).with_settings("os")

    c.save({"conanfile.py": base_conanfile("hello0")})
    c.run("export . --user=lasote --channel=stable")
    c.save({"conanfile.py": base_conanfile("hello1").with_requires("hello0/0.1@lasote/stable")})
    c.run("export . --user=lasote --channel=stable")
    c.save({"conanfile.py": base_conanfile("hello2").with_requires("hello1/0.1@lasote/stable")})
    c.run("export . --user=lasote --channel=stable")
    return c


def test_install_combined(client):
    client.run("install . --build=missing")
    client.run("install . --build=missing --build hello1/*")
    assert "hello0/0.1@lasote/stable: Already installed!" in client.out
    assert "hello1/0.1@lasote/stable: Forced build from source" in client.out


def test_install_transitive_cache(client):
    client.run("install --requires=hello2/0.1@lasote/stable --build=missing")
    assert "hello0/0.1@lasote/stable: Generating the package" in client.out
    assert "hello1/0.1@lasote/stable: Generating the package" in client.out
    assert "hello2/0.1@lasote/stable: Generating the package" in client.out


@pytest.mark.xfail(reason="build_modes.report_matches() not working now")
def test_partials(client):
    client.run("install . --build=missing")
    client.run("install ./ --build=Bye")
    assert "No package matching 'Bye' pattern found." in client.out

    for package in ["hello0", "hello1"]:
        client.run("install . --build=%s" % package)
        assert "No package matching" not in client.out


@pytest.mark.xfail(reason="changing package-ids")
def test_reuse(client):
    # FIXME: package-ids will change
    for lang, id0, id1 in [(0, "3475bd55b91ae904ac96fde0f106a136ab951a5e",
                               "c27896c40136be4bb5fd9c759d9abffaee6756a0"),
                           (1, "f43bd822487baa4ed2426c279c27b2811870499a",
                               "9f15cc4352ab4f46f118942394adc52a2cdbcffc")]:

        client.run("install . -o *:language=%d --build missing" % lang)
        assert "Configuration:[settings]", "".join(str(client.out).splitlines())
        ref = RecipeReference.loads("hello0/0.1@lasote/stable")

        hello0 = client.get_latest_pkg_layout(PkgReference(ref, id0)).package()
        hello0_info = os.path.join(hello0, CONANINFO)
        hello0_conan_info = load_binary_info(load(hello0_info))
        assert lang == hello0_conan_info["options"]["language"]

        pref1 = PkgReference(RecipeReference.loads("hello1/0.1@lasote/stable"), id1)
        hello1 = client.get_latest_pkg_layout(pref1).package()
        hello1_info = os.path.join(hello1, CONANINFO)
        hello1_conan_info = load_binary_info(load(hello1_info))
        assert lang == hello1_conan_info["options"]["language"]


def test_upper_option(client):
    client.run("install conanfile.py -o hello2*:language=1 -o hello1*:language=0 "
               "-o hello0*:language=1 --build missing")
    package_id = client.created_package_id("hello0/0.1@lasote/stable")
    package_id2 = client.created_package_id("hello1/0.1@lasote/stable")
    ref = RecipeReference.loads("hello0/0.1@lasote/stable")
    pref = client.get_latest_package_reference(ref, package_id)
    hello0 = client.get_latest_pkg_layout(pref).package()

    hello0_info = os.path.join(hello0, CONANINFO)
    hello0_conan_info = load_binary_info(load(hello0_info))
    assert "1" == hello0_conan_info["options"]["language"]

    pref1 = client.get_latest_package_reference(RecipeReference.loads("hello1/0.1@lasote/stable"), package_id2)
    hello1 = client.get_latest_pkg_layout(pref1).package()
    hello1_info = os.path.join(hello1, CONANINFO)
    hello1_conan_info = load_binary_info(load(hello1_info))
    assert "0" == hello1_conan_info["options"]["language"]


def test_inverse_upper_option(client):
    client.run("install . -o language=0 -o hello1*:language=1 -o hello0*:language=0 --build missing")
    package_id = client.created_package_id("hello0/0.1@lasote/stable")
    package_id2 = client.created_package_id("hello1/0.1@lasote/stable")
    ref = RecipeReference.loads("hello0/0.1@lasote/stable")
    pref = client.get_latest_package_reference(ref, package_id)
    hello0 = client.get_latest_pkg_layout(pref).package()

    hello0_info = os.path.join(hello0, CONANINFO)
    hello0_conan_info = load_binary_info(load(hello0_info))
    assert "0" == hello0_conan_info["options"]["language"]

    pref1 = client.get_latest_package_reference(RecipeReference.loads("hello1/0.1@lasote/stable"), package_id2)
    hello1 = client.get_latest_pkg_layout(pref1).package()
    hello1_info = os.path.join(hello1, CONANINFO)
    hello1_conan_info = load_binary_info(load(hello1_info))
    assert "1" == hello1_conan_info["options"]["language"]


def test_upper_option_txt(client):
    files = {CONANFILE_TXT: """[requires]
        hello1/0.1@lasote/stable

        [options]
        hello0*:language=1
        hello1*:language=0
        """}
    client.save(files, clean_first=True)

    client.run("install . --build missing")
    package_id = client.created_package_id("hello0/0.1@lasote/stable")
    package_id2 = client.created_package_id("hello1/0.1@lasote/stable")
    ref = RecipeReference.loads("hello0/0.1@lasote/stable")
    pref = client.get_latest_package_reference(ref, package_id)
    hello0 = client.get_latest_pkg_layout(pref).package()
    hello0_info = os.path.join(hello0, CONANINFO)
    hello0_conan_info = load_binary_info(load(hello0_info))
    assert "1" == hello0_conan_info["options"]["language"]

    pref1 = client.get_latest_package_reference(RecipeReference.loads("hello1/0.1@lasote/stable"), package_id2)
    hello1 = client.get_latest_pkg_layout(pref1).package()
    hello1_info = os.path.join(hello1, CONANINFO)
    hello1_conan_info = load_binary_info(load(hello1_info))
    assert "0" == hello1_conan_info["options"]["language"]
