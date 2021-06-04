import os


import pytest

from conans.model.info import ConanInfo
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE_TXT, CONANINFO
from conans.test.utils.tools import TestClient,  GenConanfile
from conans.util.files import save


@pytest.fixture()
def client():
    c = TestClient()
    save(c.cache.settings_path, "os: [Windows, Macos, Linux, FreeBSD]\nos_build: [Windows, Macos]")
    save(c.cache.default_profile_path, "[settings]\nos=Windows")

    def base_conanfile(name):
        return GenConanfile(name, "0.1").with_option("language", [0, 1])\
            .with_default_option("language", 0).with_settings("os")

    c.save({"conanfile.py": base_conanfile("Hello0")})
    c.run("export . lasote/stable")
    c.save({"conanfile.py": base_conanfile("Hello1").with_requires("Hello0/0.1@lasote/stable")})
    c.run("export . lasote/stable")
    c.save({"conanfile.py": base_conanfile("Hello2").with_requires("Hello1/0.1@lasote/stable")})
    c.run("export . lasote/stable")
    return c


def test_install_transitive_cache(client):
    client.run("install Hello2/0.1@lasote/stable --build=missing")
    assert "Hello0/0.1@lasote/stable: Generating the package" in client.out
    assert "Hello1/0.1@lasote/stable: Generating the package" in client.out
    assert "Hello2/0.1@lasote/stable: Generating the package" in client.out


def test_partials(client):
    client.run("install . --build=missing")
    client.run("install ./ --build=Bye")
    assert "No package matching 'Bye' pattern" in client.out

    for package in ["Hello0", "Hello1"]:
        client.run("install . --build=%s" % package)
        assert "No package matching" not in client.out


@pytest.mark.xfail(reason="cache2.0")
def test_reuse(client):
    for lang, id0, id1 in [(0, "3475bd55b91ae904ac96fde0f106a136ab951a5e",
                               "5faecfb46fd09e49f1812d732d6360bc1663e3ab"),
                           (1, "f43bd822487baa4ed2426c279c27b2811870499a",
                               "b96337c5fcdafd6533298017c2ba94812654f8ec")]:

        client.run("install . -o *:language=%d --build missing" % lang)
        assert "Configuration:[settings]", "".join(str(client.out).splitlines())
        ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")

        hello0 = client.cache.package_layout(ref).package(PackageReference(ref, id0))
        hello0_info = os.path.join(hello0, CONANINFO)
        hello0_conan_info = ConanInfo.load_file(hello0_info)
        assert lang == hello0_conan_info.options.language

        pref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"), id1)
        hello1 = client.cache.package_layout(pref1.ref).package(pref1)
        hello1_info = os.path.join(hello1, CONANINFO)
        hello1_conan_info = ConanInfo.load_file(hello1_info)
        assert lang == hello1_conan_info.options.language


def test_upper_option(client):
    client.run("install conanfile.py -o Hello2:language=1 -o Hello1:language=0 "
               "-o Hello0:language=1 --build missing")
    ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")

    pref = PackageReference(ref, "f43bd822487baa4ed2426c279c27b2811870499a")
    hello0 = client.cache.package_layout(ref).package(pref)

    hello0_info = os.path.join(hello0, CONANINFO)
    hello0_conan_info = ConanInfo.load_file(hello0_info)
    assert 1 == hello0_conan_info.options.language

    pref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"),
                             "5faecfb46fd09e49f1812d732d6360bc1663e3ab")
    hello1 = client.cache.package_layout(pref1.ref).package(pref1)
    hello1_info = os.path.join(hello1, CONANINFO)
    hello1_conan_info = ConanInfo.load_file(hello1_info)
    assert 0 == hello1_conan_info.options.language


def test_inverse_upper_option(client):
    client.run("install . -o language=0 -o Hello1:language=1 -o Hello0:language=0 --build missing")

    ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
    pref = PackageReference(ref, "3475bd55b91ae904ac96fde0f106a136ab951a5e")
    hello0 = client.cache.package_layout(ref).package(pref)

    hello0_info = os.path.join(hello0, CONANINFO)
    hello0_conan_info = ConanInfo.load_file(hello0_info)
    assert "language=0" == hello0_conan_info.options.dumps()

    pref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"),
                             "b96337c5fcdafd6533298017c2ba94812654f8ec")
    hello1 = client.cache.package_layout(pref1.ref).package(pref1)
    hello1_info = os.path.join(hello1, CONANINFO)
    hello1_conan_info = ConanInfo.load_file(hello1_info)
    assert "language=1" == hello1_conan_info.options.dumps()


def test_upper_option_txt(client):
    files = {CONANFILE_TXT: """[requires]
        Hello1/0.1@lasote/stable

        [options]
        Hello0:language=1
        Hello1:language=0
        """}
    client.save(files, clean_first=True)

    client.run("install . --build missing")
    ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
    pref = PackageReference(ref, "f43bd822487baa4ed2426c279c27b2811870499a")
    hello0 = client.cache.package_layout(ref).package(pref)
    hello0_info = os.path.join(hello0, CONANINFO)
    hello0_conan_info = ConanInfo.load_file(hello0_info)
    assert 1 == hello0_conan_info.options.language

    pref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"),
                             "5faecfb46fd09e49f1812d732d6360bc1663e3ab")
    hello1 = client.cache.package_layout(pref1.ref).package(pref1)
    hello1_info = os.path.join(hello1, CONANINFO)
    hello1_conan_info = ConanInfo.load_file(hello1_info)
    assert 0 == hello1_conan_info.options.language


def test_cross_platform_msg(client):
    # Explicit with os_build and os_arch settings
    client.run("install Hello0/0.1@lasote/stable -s:b os=Macos -s:h os=Windows", assert_error=True)
    assert "Cross-build from 'Macos:None' to 'Windows:None'" in client.out
    assert "ERROR: Missing binary: Hello0" in client.out
