import os
import platform
import re

import pytest

from conans.client.tools.oss import detected_os
from conans.model.info import ConanInfo
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE_TXT, CONANINFO
from conans.test.utils.tools import TestClient,  GenConanfile
from conans.util.files import save


@pytest.fixture()
def client():
    c = TestClient()
    save(c.cache.settings_path, "os: [Windows, Macos, Linux, FreeBSD]\nos_build: [Windows, Macos]\narch_build: [x86_64]")
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


def test_install_combined(client):
    client.run("install . --build=missing")
    client.run("install . --build=missing --build Hello1")
    assert "Hello0/0.1@lasote/stable: Already installed!" in client.out
    assert "Hello1/0.1@lasote/stable: Forced build from source" in client.out


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


def test_reuse(client):
    for lang, id0, id1 in [(0, "3475bd55b91ae904ac96fde0f106a136ab951a5e",
                               "5faecfb46fd09e49f1812d732d6360bc1663e3ab"),
                           (1, "f43bd822487baa4ed2426c279c27b2811870499a",
                               "b96337c5fcdafd6533298017c2ba94812654f8ec")]:

        client.run("install . -o *:language=%d --build missing" % lang)
        assert "Configuration:[settings]", "".join(str(client.out).splitlines())
        info_path = os.path.join(client.current_folder, CONANINFO)
        conan_info = ConanInfo.load_file(info_path)
        assert "os=Windows" == conan_info.settings.dumps()
        assert "language=%s" % lang, conan_info.options.dumps()
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
    package_id = re.search(r"Hello0/0.1@lasote/stable:(\S+)", str(client.out)).group(1)
    package_id2 = re.search(r"Hello1/0.1@lasote/stable:(\S+)", str(client.out)).group(1)
    info_path = os.path.join(client.current_folder, CONANINFO)
    conan_info = ConanInfo.load_file(info_path)
    assert "language=1" == conan_info.options.dumps()
    ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")

    pref = PackageReference(ref, package_id)
    hello0 = client.cache.package_layout(ref).package(pref)

    hello0_info = os.path.join(hello0, CONANINFO)
    hello0_conan_info = ConanInfo.load_file(hello0_info)
    assert 1 == hello0_conan_info.options.language

    pref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"), package_id2)
    hello1 = client.cache.package_layout(pref1.ref).package(pref1)
    hello1_info = os.path.join(hello1, CONANINFO)
    hello1_conan_info = ConanInfo.load_file(hello1_info)
    assert 0 == hello1_conan_info.options.language


def test_inverse_upper_option(client):
    client.run("install . -o language=0 -o Hello1:language=1 -o Hello0:language=0 --build missing")
    package_id = re.search(r"Hello0/0.1@lasote/stable:(\S+)", str(client.out)).group(1)
    package_id2 = re.search(r"Hello1/0.1@lasote/stable:(\S+)", str(client.out)).group(1)
    info_path = os.path.join(client.current_folder, CONANINFO)

    conan_info = ConanInfo.load_file(info_path)

    assert "language=0" == conan_info.options.dumps()
    ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
    pref = PackageReference(ref, package_id)
    hello0 = client.cache.package_layout(ref).package(pref)

    hello0_info = os.path.join(hello0, CONANINFO)
    hello0_conan_info = ConanInfo.load_file(hello0_info)
    assert "language=0" == hello0_conan_info.options.dumps()

    pref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"), package_id2)
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
    package_id = re.search(r"Hello0/0.1@lasote/stable:(\S+)", str(client.out)).group(1)
    package_id2 = re.search(r"Hello1/0.1@lasote/stable:(\S+)", str(client.out)).group(1)
    info_path = os.path.join(client.current_folder, CONANINFO)
    conan_info = ConanInfo.load_file(info_path)
    assert "" == conan_info.options.dumps()
    ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
    pref = PackageReference(ref, package_id)
    hello0 = client.cache.package_layout(ref).package(pref)
    hello0_info = os.path.join(hello0, CONANINFO)
    hello0_conan_info = ConanInfo.load_file(hello0_info)
    assert 1 == hello0_conan_info.options.language

    pref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"), package_id2)
    hello1 = client.cache.package_layout(pref1.ref).package(pref1)
    hello1_info = os.path.join(hello1, CONANINFO)
    hello1_conan_info = ConanInfo.load_file(hello1_info)
    assert 0 == hello1_conan_info.options.language


def test_change_option_txt(client):
    # Do not adjust cpu_count, it is reusing a cache
    client = TestClient(cache_folder=client.cache_folder, cpu_count=False)
    files = {CONANFILE_TXT: """[requires]
        Hello0/0.1@lasote/stable

        [options]
        Hello0:language=1
        """}
    client.save(files)

    client.run("install conanfile.txt --build missing")
    info_path = os.path.join(client.current_folder, CONANINFO)
    conan_info = ConanInfo.load_file(info_path)
    assert "" == conan_info.options.dumps()
    assert "Hello0:language=1" == conan_info.full_options.dumps()
    assert "Hello0/0.1@lasote/stable:f43bd822487baa4ed2426c279c27b2811870499a" ==\
           conan_info.full_requires.dumps()

    files = {CONANFILE_TXT: """[requires]
        Hello0/0.1@lasote/stable

        [options]
        Hello0:language=0
        """}
    client.save(files)
    client.run("install . --build missing")

    info_path = os.path.join(client.current_folder, CONANINFO)
    conan_info = ConanInfo.load_file(info_path)
    assert "" == conan_info.options.dumps()
    # For conan install options are not cached anymore
    assert "Hello0:language=0" == conan_info.full_options.dumps()

    # it is necessary to clean the cached conaninfo
    client.save(files, clean_first=True)
    client.run("install ./conanfile.txt --build missing")
    conan_info = ConanInfo.load_file(info_path)
    assert "" == conan_info.options.dumps()
    assert "Hello0:language=0" == conan_info.full_options.dumps()
    assert "Hello0/0.1@lasote/stable:3475bd55b91ae904ac96fde0f106a136ab951a5e" \
           == conan_info.full_requires.dumps()


def test_cross_platform_msg(client):
    # Explicit with os_build and os_arch settings
    client.run("install Hello0/0.1@lasote/stable -s os_build=Macos -s arch_build=x86_64 -s os=Windows", assert_error=True)
    assert "Cross-build from 'Macos:x86_64' to 'Windows:None'" in client.out
    assert "ERROR: Missing binary: Hello0" in client.out

    bad_os = "Windows" if platform.system() != "Windows" else "Macos"
    client.run("install Hello0/0.1@lasote/stable -s os={} -s arch_build=x86_64".format(bad_os), assert_error=True)
    # Implicit detection when not available (retrocompatibility)
    message = "Cross-build from '{}:x86_64' to '{}:None'".format(detected_os(), bad_os)
    assert message in client.out
