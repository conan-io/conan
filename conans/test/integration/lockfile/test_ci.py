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
    files = {
        "pkga/conanfile.py": conanfile.format(requires=""),
        "pkga/myfile.txt": "HelloA",
        "pkgj/conanfile.py": conanfile.format(requires=""),
        "pkgj/myfile.txt": "HelloJ",
        "pkgb/conanfile.py": conanfile.format(requires='requires="pkga/[>0.0 <1.0]"'),
        "pkgb/myfile.txt": "HelloB",
        "pkgc/conanfile.py": conanfile.format(requires='requires="pkgb/[>0.0 <1.0]"'),
        "pkgc/myfile.txt": "HelloC",
        "app1/conanfile.py": conanfile.format(requires='requires="pkgc/[>0.0 <1.0]"'),
        "app1/myfile.txt": "App1",
    }
    client.save(files)

    client.run("create pkga pkga/0.1@ -s os=Windows")
    client.run("create pkga pkga/0.1@ -s os=Linux")
    client.run("create pkgb pkgb/0.1@ -s os=Windows")
    client.run("create pkgc pkgc/0.1@ -s os=Windows")
    client.run("create app1 app1/0.1@ -s os=Windows")
    assert "app1/0.1: SELF FILE: App1" in client.out
    assert "app1/0.1: DEP FILE pkga: HelloA" in client.out
    assert "app1/0.1: DEP FILE pkgb: HelloB" in client.out
    assert "app1/0.1: DEP FILE pkgc: HelloC" in client.out
    return client


def test_single_config_centralized(client_setup):
    client = client_setup
    # capture the initial lockfile of our product
    client.run("lock create --reference=app1/0.1@  --lockfile-out=app1.lock -s os=Windows")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    client.save({"pkga/myfile.txt": "ByeA World!!"})
    client.run("create pkga pkga/0.2@ -s os=Windows")

    # Do a change in B, this is the change that we want to test
    client.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.2 works
    client.run("create pkgb pkgb/0.2@ -s os=Windows "
               "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/0.2: DEP FILE pkga: HelloA" in client.out

    # Now lets build the application, to see everything ok
    client.run("install app1/0.1@  --lockfile=app1_b_changed.lock "
               "--lockfile-out=app1_b_integrated.lock "
               "--build=missing  -s os=Windows")
    assert "pkgb/0.2:22b971c0de07d512bbbd9a6b52f30c173a16d5c3 - Cache" in client.out
    assert "pkgc/0.1:24cd3a442376283b9a4b11b6c7ddf07f4d43adb1 - Build" in client.out
    assert "app1/0.1:44561b1ea2dc5aaccdfdf9876dc105026d02b1a7 - Build" in client.out
    assert "pkgb/0.2" in client.out
    assert "pkgb/0.1" not in client.out
    assert "app1/0.1: DEP FILE pkga: HelloA" in client.out
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
    client.run("create pkga pkga/0.2@ -s os=Windows")

    # Do a change in B, this is the change that we want to test
    client.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/1.0 works (but it is out of valid range!)
    client.run("create pkgb pkgb/1.0@ -s os=Windows "
               "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/1.0: DEP FILE pkga: HelloA" in client.out

    # Now lets build the application, to see everything ok
    client.run("install app1/0.1@  --lockfile=app1_b_changed.lock "
               "--lockfile-out=app1_b_integrated.lock "
               "--build=missing  -s os=Windows")
    # Nothing changed, the change is outside the range, app1 not affected!!
    assert "pkgb/0.1:22b971c0de07d512bbbd9a6b52f30c173a16d5c3 - Cache" in client.out
    assert "pkgc/0.1:9f6e1cc6394b56083a15be3cd15986afecf60af4 - Cache" in client.out
    assert "app1/0.1:7d8f68f180f24d339ea6ff83da733af54e4a5233 - Cache" in client.out
    assert "pkgb/0.2" not in client.out
    assert "app1/0.1: DEP FILE pkga: HelloA" in client.out
    assert "app1/0.1: DEP FILE pkgb: HelloB" in client.out

    # All good! We can get rid of the now unused pkgb/1.0 version in the lockfile
    client.run("lock create --reference=app1/0.1@ --lockfile=app1_b_integrated.lock "
               "--lockfile-out=app1_clean.lock -s os=Windows --clean")
    app1_clean = client.load("app1_clean.lock")
    assert "pkgb/0.1" in app1_clean
    assert "pkgb/1.0" not in app1_clean


@pytest.mark.xfail(reason="lockfiles wip")
def test_single_config_centralized_change_dep_version(client_setup):
    client = client_setup
    client.run("lock create --reference=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    client.save({"pkga/myfile.txt": "ByeA World!!"})
    client.run("create pkga pkga/0.2@ -s os=Windows")

    # Build new package alternative J
    client.run("create pkgj pkgj/0.1@ -s os=Windows")

    # Do a change in B, this is the change that we want to test
    client.save({"pkgb/conanfile.py": conanfile.format(requires=
                                                       'requires="pkgj/[>0.0 <1.0]"'),
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


@pytest.mark.xfail(reason="lockfiles wip")
def test_multi_config_centralized(client_setup):
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

    # Now lets build the application, to see everything ok
    client.run("lock install b_win.lock --lockfile-out=pkgd2_win.lock --build=missing")
    print(client.out)
    assert "SELF OS: Windows!!" in client.out
    assert "SELF OS: Linux!!" not in client.out
    assert "pkgb/0.2" in client.out
    assert "pkgb/0.1" not in client.out
    assert "pkgd/0.1: DEP FILE pkga: HelloA" in client.out
    assert "pkgd/0.1: DEP FILE pkgb: ByeB World!!" in client.out

    pkgd2_lockfile = client.load("pkgd2_win.lock")
    print(pkgd2_lockfile)
    assert "pkgb/0.2" in pkgd2_lockfile
    assert "pkgb/0.1" not in pkgd2_lockfile

    client.run("lock install b_linux.lock --lockfile-out=pkgd2_linux.lock --build=missing")
    print(client.out)
    assert "SELF OS: Windows!!" not in client.out
    assert "SELF OS: Linux!!" in client.out
    assert "pkgb/0.2" in client.out
    assert "pkgb/0.1" not in client.out
    assert "pkgd/0.1: DEP FILE pkga: HelloA" in client.out
    assert "pkgd/0.1: DEP FILE pkgb: ByeB World!!" in client.out

    pkgd2_lockfile = client.load("pkgd2_win.lock")
    print(pkgd2_lockfile)
    assert "pkgb/0.2" in pkgd2_lockfile
    assert "pkgb/0.1" not in pkgd2_lockfile


@pytest.mark.xfail(reason="lockfiles wip")
def test_multi_config_decentralized(client_setup):
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

    for ref, _, _, _ in to_build:
        print("******************** building: ", ref, "***************************")
        client_aux = TestClient(cache_folder=client.cache_folder)
        client_aux.save({"temp.lock": lock_fileaux})
        client_aux.run("install %s --build=%s --lockfile=temp.lock " % (ref, ref))
        print(client_aux.out)
        assert "SELF OS: Windows!!" in client_aux.out
        assert "pkgb/0.2" in client_aux.out
        assert "pkgb/0.1" not in client_aux.out
        assert "DEP FILE pkga: HelloA" in client_aux.out
        assert "DEP FILE pkgb: ByeB World!!" in client_aux.out


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
