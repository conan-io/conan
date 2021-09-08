import json
import textwrap

import pytest

from conans.test.utils.tools import TestClient


conanfile = textwrap.dedent("""
    from conans import ConanFile, load
    import os
    class Pkg(ConanFile):
        settings = "os"
        {requires}
        exports_sources = "myfile.txt"
        keep_imports = True
        def imports(self):
            self.copy("myfile.txt", folder=True)
        def package(self):
            self.copy("*myfile.txt")
        def package_info(self):
            self.output.info("SELF OS: %s!!" % self.settings.os)
            self.output.info("SELF FILE: %s"
                % load(os.path.join(self.package_folder, "myfile.txt")))
            for d in os.listdir(self.package_folder):
                p = os.path.join(self.package_folder, d, "myfile.txt")
                if os.path.isfile(p):
                    self.output.info("DEP FILE %s: %s" % (d, load(p)))
        """)


@pytest.fixture()
def client_setup():
    client = TestClient()
    client.run("config set general.default_package_id_mode=full_package_mode")
    pkb_requirements = """
    def requirements(self):
        if self.settings.os == "Windows":
            self.requires("pkgawin/[>0.0 <1.0]")
        else:
            self.requires("pkganix/[>0.0 <1.0]")
    """
    files = {
        "pkga/conanfile.py": conanfile.format(requires=""),
        "pkga/myfile.txt": "HelloA",
        "pkgj/conanfile.py": conanfile.format(requires=""),
        "pkgj/myfile.txt": "HelloJ",
        "pkgb/conanfile.py": conanfile.format(requires=pkb_requirements),
        "pkgb/myfile.txt": "HelloB",
        "pkgc/conanfile.py": conanfile.format(requires='requires="pkgb/[>0.0 <1.0]"'),
        "pkgc/myfile.txt": "HelloC",
        "app1/conanfile.py": conanfile.format(requires='requires="pkgc/[>0.0 <1.0]"'),
        "app1/myfile.txt": "App1",
    }
    client.save(files)

    client.run("create pkga pkgawin/0.1@ -s os=Windows")
    client.run("create pkga pkganix/0.1@ -s os=Linux")
    client.run("create pkgb pkgb/0.1@ -s os=Windows")
    client.run("create pkgc pkgc/0.1@ -s os=Windows")
    client.run("create app1 app1/0.1@ -s os=Windows")
    assert "app1/0.1: SELF FILE: App1" in client.out
    assert "app1/0.1: DEP FILE pkgawin: HelloA" in client.out
    assert "app1/0.1: DEP FILE pkgb: HelloB" in client.out
    assert "app1/0.1: DEP FILE pkgc: HelloC" in client.out
    return client


def test_single_config_centralized(client_setup):
    client = client_setup
    # capture the initial lockfile of our product
    client.run("lock create --reference=app1/0.1@  --lockfile-out=app1.lock -s os=Windows")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    client.save({"pkga/myfile.txt": "ByeA World!!"})
    client.run("create pkga pkgawin/0.2@ -s os=Windows")

    # Do a change in B, this is the change that we want to test
    client.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.2 works
    client.run("create pkgb pkgb/0.2@ -s os=Windows "
               "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/0.2: DEP FILE pkgawin: HelloA" in client.out

    # Now lets build the application, to see everything ok
    client.run("install app1/0.1@  --lockfile=app1_b_changed.lock "
               "--lockfile-out=app1_b_integrated.lock "
               "--build=missing  -s os=Windows")
    assert "pkgawin/0.1:cf2e4ff978548fafd099ad838f9ecb8858bf25cb - Cache" in client.out
    assert "pkgb/0.2:bf0518650d942fd1fad0c359bcba1d832682e64b - Cache" in client.out
    assert "pkgc/0.1:5c677c308daaa52d869a58a77500ed33e0fbc0ba - Build" in client.out
    assert "app1/0.1:570be7df332d2320b566b83489e4468d03dfd88a - Build" in client.out
    assert "pkgb/0.2" in client.out
    assert "pkgb/0.1" not in client.out
    assert "app1/0.1: DEP FILE pkgawin: HelloA" in client.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in client.out

    # All good! We can get rid of the now unused pkgb/0.1 version in the lockfile
    client.run("lock create --reference=app1/0.1@ --lockfile=app1_b_integrated.lock "
               "--lockfile-out=app1_clean.lock -s os=Windows --clean")
    app1_clean = client.load("app1_clean.lock")
    assert "pkgb/0.2" in app1_clean
    assert "pkgb/0.1" not in app1_clean


def test_single_config_centralized_out_range(client_setup):
    client = client_setup
    client.run("lock create --reference=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    client.save({"pkga/myfile.txt": "ByeA World!!"})
    client.run("create pkga pkgawin/0.2@ -s os=Windows")

    # Do a change in B, this is the change that we want to test
    client.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/1.0 works (but it is out of valid range!)
    client.run("create pkgb pkgb/1.0@ -s os=Windows "
               "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/1.0: DEP FILE pkgawin: HelloA" in client.out

    # Now lets build the application, to see everything ok
    client.run("install app1/0.1@  --lockfile=app1_b_changed.lock "
               "--lockfile-out=app1_b_integrated.lock "
               "--build=missing  -s os=Windows")
    # Nothing changed, the change is outside the range, app1 not affected!!
    assert "pkgawin/0.1:cf2e4ff978548fafd099ad838f9ecb8858bf25cb - Cache" in client.out
    assert "pkgb/0.1:bf0518650d942fd1fad0c359bcba1d832682e64b - Cache" in client.out
    assert "pkgc/0.1:a55e51982e7ba0fb0c08b74e99fdb47abb95ae33 - Cache" in client.out
    assert "app1/0.1:d9b0acfe99a36ba30ea619415e8392bf79736163 - Cache" in client.out
    assert "pkgb/0.2" not in client.out
    assert "app1/0.1: DEP FILE pkgawin: HelloA" in client.out
    assert "app1/0.1: DEP FILE pkgb: HelloB" in client.out

    # All good! We can get rid of the now unused pkgb/1.0 version in the lockfile
    client.run("lock create --reference=app1/0.1@ --lockfile=app1_b_integrated.lock "
               "--lockfile-out=app1_clean.lock -s os=Windows --clean")
    app1_clean = client.load("app1_clean.lock")
    assert "pkgb/0.1" in app1_clean
    assert "pkgb/1.0" not in app1_clean


def test_single_config_centralized_change_dep(client_setup):
    client = client_setup
    client.run("lock create --reference=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    client.save({"pkga/myfile.txt": "ByeA World!!"})
    client.run("create pkga pkgawin/0.2@ -s os=Windows")

    # Build new package alternative J
    client.run("create pkgj pkgj/0.1@ -s os=Windows")

    # Do a change in B, this is the change that we want to test
    client.save({"pkgb/conanfile.py": conanfile.format(requires='requires="pkgj/[>0.0 <1.0]"'),
                 "pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.2 works
    client.run("create pkgb pkgb/0.2@ -s os=Windows "
               "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/0.2: DEP FILE pkgj: HelloJ" in client.out
    # Build new package alternative J, it won't be included, already locked in this create
    client.run("create pkgj pkgj/0.2@ -s os=Windows")

    # Now lets build the application, to see everything ok
    client.run("install app1/0.1@  --lockfile=app1_b_changed.lock "
               "--lockfile-out=app1_b_integrated.lock "
               "--build=missing  -s os=Windows")
    assert "pkga" not in client.out
    assert "pkgj/0.1:cf2e4ff978548fafd099ad838f9ecb8858bf25cb - Cache" in client.out
    assert "pkgb/0.2:a2975e79c48a00781132d2ec57bd8d9416e81abe - Cache" in client.out
    assert "pkgc/0.1:19cf7301aa609fce0561d42bd42f685555b58ba2 - Build" in client.out
    assert "app1/0.1:ba387b6f1ed67a4b0eb953de1d1a74b8d4e62884 - Build" in client.out
    assert "app1/0.1: DEP FILE pkgj: HelloJ" in client.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in client.out

    # All good! We can get rid of the now unused pkgb/1.0 version in the lockfile
    client.run("lock create --reference=app1/0.1@ --lockfile=app1_b_integrated.lock "
               "--lockfile-out=app1_clean.lock -s os=Windows --clean")
    app1_clean = client.load("app1_clean.lock")
    assert "pkgj/0.1" in app1_clean
    assert "pkgb/0.2" in app1_clean
    assert "pkgb/0.1" not in app1_clean


def test_multi_config_centralized(client_setup):
    client = client_setup
    # capture the initial lockfile of our product
    client.run("lock create --reference=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")
    client.run("lock create --reference=app1/0.1@ --lockfile=app1.lock --lockfile-out=app1.lock "
               "-s os=Linux")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    client.save({"pkga/myfile.txt": "ByeA World!!"})
    client.run("create pkga pkgawin/0.2@ -s os=Windows")
    client.run("create pkga pkganix/0.2@ -s os=Linux")

    # Do a change in B, this is the change that we want to test
    client.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.2 works
    client.run("create pkgb pkgb/0.2@ -s os=Windows "
               "--lockfile=app1.lock --lockfile-out=app1_win.lock")
    assert "pkgb/0.2: DEP FILE pkgawin: HelloA" in client.out
    client.run("create pkgb pkgb/0.2@ -s os=Linux "
               "--lockfile=app1.lock --lockfile-out=app1_nix.lock")
    assert "pkgb/0.2: DEP FILE pkganix: HelloA" in client.out

    # Now lets build the application, to see everything ok
    client.run("install app1/0.1@  --lockfile=app1_win.lock --lockfile-out=app1_win.lock "
               "--build=missing  -s os=Windows")
    assert "pkgawin/0.1:cf2e4ff978548fafd099ad838f9ecb8858bf25cb - Cache" in client.out
    assert "pkgb/0.2:bf0518650d942fd1fad0c359bcba1d832682e64b - Cache" in client.out
    assert "pkgc/0.1:5c677c308daaa52d869a58a77500ed33e0fbc0ba - Build" in client.out
    assert "app1/0.1:570be7df332d2320b566b83489e4468d03dfd88a - Build" in client.out
    assert "pkgb/0.2" in client.out
    assert "pkgb/0.1" not in client.out
    assert "app1/0.1: DEP FILE pkgawin: HelloA" in client.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in client.out

    # Now lets build the application, to see everything ok
    client.run("install app1/0.1@  --lockfile=app1_nix.lock --lockfile-out=app1_nix.lock "
               "--build=missing  -s os=Linux")
    assert "pkganix/0.1:02145fcd0a1e750fb6e1d2f119ecdf21d2adaac8 - Cache" in client.out
    assert "pkgb/0.2:d169a8a97fd0ef581801b24d7c61a9afb933aa13 - Cache" in client.out
    assert "pkgc/0.1:0796c8d93fa07b543df4479cc0309631dc0cd8fa - Build" in client.out
    assert "app1/0.1:1674d669f4416c10e32da07b06ea1909e376a458 - Build" in client.out
    assert "pkgb/0.2" in client.out
    assert "pkgb/0.1" not in client.out
    assert "app1/0.1: DEP FILE pkganix: HelloA" in client.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in client.out

    # All good! We can get rid of the now unused pkgb/0.1 version in the lockfile
    client.run("lock create --reference=app1/0.1@ --lockfile=app1_win.lock "
               "--lockfile-out=app1_win.lock -s os=Windows --clean")
    app1_clean = client.load("app1_win.lock")
    assert "pkgawin/0.1" in app1_clean
    assert "pkgb/0.2" in app1_clean
    assert "pkgb/0.1" not in app1_clean
    assert "pkgawin/0.2" not in app1_clean
    assert "pkganix/0.2" not in app1_clean
    client.run("lock create --reference=app1/0.1@ --lockfile=app1_nix.lock "
               "--lockfile-out=app1_nix.lock -s os=Linux --clean")
    app1_clean = client.load("app1_nix.lock")
    assert "pkganix/0.1" in app1_clean
    assert "pkgb/0.2" in app1_clean
    assert "pkgb/0.1" not in app1_clean
    assert "pkgawin/0.2" not in app1_clean
    assert "pkganix/0.2" not in app1_clean

    # Finally, merge the 2 clean lockfiles, for keeping just 1 for next iteration
    client.run("lock merge --lockfile=app1_win.lock --lockfile=app1_nix.lock "
               "--lockfile-out=app1_final.lock")
    app1_clean = client.load("app1_final.lock")
    assert "pkgawin/0.1" in app1_clean
    assert "pkganix/0.1" in app1_clean
    assert "pkgb/0.2" in app1_clean
    assert "pkgb/0.1" not in app1_clean
    assert "pkgawin/0.2" not in app1_clean
    assert "pkganix/0.2" not in app1_clean


def test_single_config_decentralized(client_setup):
    client = client_setup
    # capture the initial lockfile of our product
    client.run("lock create --reference=app1/0.1@  --lockfile-out=app1.lock -s os=Windows")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    client.save({"pkga/myfile.txt": "ByeA World!!"})
    client.run("create pkga pkgawin/0.2@ -s os=Windows")

    # Do a change in B, this is the change that we want to test
    client.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.2 works
    client.run("create pkgb pkgb/0.2@ -s os=Windows "
               "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/0.2: DEP FILE pkgawin: HelloA" in client.out

    # Now lets build the application, to see everything ok
    client.run("info app1/0.1@ --lockfile=app1_b_changed.lock --dry-build=missing "
               "--build-order=build_order.json")
    json_file = client.load("build_order.json")
    assert "app1/0.1" in json_file
    assert "pkgc/0.1" in json_file
    assert "pkga" not in json_file
    assert "pkgb" not in json_file
    to_build = json.loads(json_file)

    for ref, _, _, _ in to_build:
        client.run("install %s --build=%s --lockfile=app1_b_changed.lock " % (ref, ref))

        assert "pkgawin/0.1:cf2e4ff978548fafd099ad838f9ecb8858bf25cb - Cache" in client.out
        assert "pkgb/0.2:bf0518650d942fd1fad0c359bcba1d832682e64b - Cache" in client.out
        assert "pkgb/0.2" in client.out
        assert "pkgb/0.1" not in client.out
        assert "DEP FILE pkgawin: HelloA" in client.out
        assert "DEP FILE pkgb: ByeB World!!"


@pytest.mark.xfail(reason="lockfiles wip")
def test_multi_config_bundle(client_setup):
    client = client_setup
    client.run("lock create --reference=pkgd/0.1@ --lockfile-out=pkgd.lock "
               "-s os=Windows ")
    pkgd_lockfile = client.load("pkgd.lock")
    print(pkgd_lockfile)

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    client.save({"pkga/myfile.txt": "ByeA World!!"})
    client.run("create pkga pkga/0.2@ -s os=Windows")

    # Do a change in B, this is the change that we want to test
    client.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.2 works
    client.run("create pkgb pkgb/0.2@ -s os=Windows "
               "--lockfile=pkgd.lock --lockfile-out=b_win.lock")
    assert "SELF OS: Windows!!" in client.out
    assert "pkgb/0.2: DEP FILE pkga: HelloA" in client.out
    b_win = client.load("b_win.lock")
    print(b_win)
    client.run("create pkgb pkgb/0.2@ -s os=Linux "
               "--lockfile=pkgd.lock --lockfile-out=b_linux.lock")
    assert "SELF OS: Linux!!" in client.out
    assert "pkgb/0.2: DEP FILE pkga: HelloA" in client.out
    b_linux = client.load("b_linux.lock")
    print(b_linux)

    # To bundle, lockfiles should be complete?
    client.run("lock bundle create b_win.lock b_linux.lock")
    print(client.load("lock.bundle"))
    return

    # Now lets build the application, to see everything ok
    client.run("lock build-order b_win.lock --lockfile-out=pkgd2_win.lock --build=missing "
               "--json=build_order.json")
    print(client.out)
    assert "pkgb/0.2" in client.out
    assert "pkgb/0.1" not in client.out

    pkgd2_lockfile = client.load("pkgd2_win.lock")
    print(pkgd2_lockfile)
    assert "pkgb/0.2" in pkgd2_lockfile
    assert "pkgb/0.1" not in pkgd2_lockfile

    json_file = client.load("build_order.json")
    print("JSON: ", json_file)
    to_build = json.loads(json_file)
    lock_fileaux = pkgd2_lockfile

    for ref, _, _ in to_build:
        print("******************** building: ", ref, "***************************")
        client_aux = TestClient(cache_folder=client.cache_folder)
        client_aux.save({"temp.lock": lock_fileaux})
        client_aux.run("install %s --build=%s --lockfile=temp.lock " % (ref, ref))
        print(client_aux.out)
        assert "SELF OS: Windows!!" in client_aux.out
        assert "pkgb/0.2" in client_aux.out
        assert "pkgb/0.1" not in client_aux.out
        assert "DEP FILE pkga: HelloA" in client_aux.out
