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
    client.run("lock create --reference=app1/0.1@  --lockfile-out=app1.lock -s os=Windows")
    app1_lockfile = client.load("app1.lock")
    print(app1_lockfile)

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    client.save({"pkga/myfile.txt": "ByeA World!!"})
    client.run("create pkga pkga/0.2@ -s os=Windows")

    # Do a change in B, this is the change that we want to test
    client.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.2 works
    client.run("create pkgb pkgb/0.2@ -s os=Windows "
               "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/0.2: DEP FILE pkga: HelloA" in client.out
    b_win = client.load("app1_b_changed.lock")
    print(b_win)

    # Now lets build the application, to see everything ok
    client.run("lock install app1_b_changed.lock --lockfile-out=app1_b_integrated.lock "
               "--build=missing")
    print(client.out)
    assert "pkgb/0.2" in client.out
    assert "pkgb/0.1" not in client.out
    assert "pkgd/0.1: DEP FILE pkga: HelloA" in client.out
    assert "pkgd/0.1: DEP FILE pkgb: ByeB World!!" in client.out

    app1_b_integrated = client.load("app1_b_integrated.lock")
    print(app1_b_integrated)
    assert "pkgb/0.2" in app1_b_integrated
    assert "pkgb/0.1" not in app1_b_integrated


def test_single_config_centralized_out_range(client_setup):
    client = client_setup
    client.run("lock create --reference=pkgd/0.1@ --lockfile-out=pkgd.lock "
               "-s os=Windows")
    pkgd_lockfile = client.load("pkgd.lock")
    print(pkgd_lockfile)

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    client.save({"pkga/myfile.txt": "ByeA World!!"})
    client.run("create pkga pkga/0.2@ -s os=Windows")

    # Do a change in B, this is the change that we want to test
    client.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.2 works
    client.run("create pkgb pkgb/1.0@ -s os=Windows "
               "--lockfile=pkgd.lock --lockfile-out=b_win.lock")
    assert "pkgb/1.0: DEP FILE pkga: HelloA" in client.out
    b_win = client.load("b_win.lock")
    print(b_win)

    # Now lets build the application, to see everything ok
    client.run("lock install b_win.lock --lockfile-out=pkgd2.lock --build=missing")
    print(client.out)
    assert "pkgb/0.1" in client.out
    assert "pkgb/1.0" not in client.out

    pkgd2_lockfile = client.load("pkgd2.lock")
    print(pkgd2_lockfile)
    assert "pkgb/0.1" in pkgd2_lockfile
    assert "pkgb/1.0" not in pkgd2_lockfile


def test_single_config_centralized_change_dep_version(client_setup):
    client = client_setup
    client.run("lock create --reference=pkgd/0.1@ --lockfile-out=pkgd.lock "
               "-s os=Windows")
    pkgd_lockfile = client.load("pkgd.lock")
    print(pkgd_lockfile)

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    client.save({"pkga/myfile.txt": "ByeA World!!"})
    client.run("create pkga pkga/0.2@ -s os=Windows")

    # Build new package alternative J
    client.run("create pkgj PkgJ/0.1@ -s os=Windows")

    # Do a change in B, this is the change that we want to test
    client.save({"pkgb/conanfile.py": conanfile.format(requires=
                                                       'requires="PkgJ/[>0.0 <1.0]"'),
                 "pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.2 works
    client.run("create pkgb pkgb/0.2@ -s os=Windows "
               "--lockfile=pkgd.lock --lockfile-out=b_win.lock")
    assert "pkgb/0.2: DEP FILE PkgJ: HelloJ" in client.out
    b_win = client.load("b_win.lock")
    print(b_win)

    # Now lets build the application, to see everything ok
    client.run("lock install b_win.lock --lockfile-out=pkgd2.lock --build=missing")
    print(client.out)
    assert "pkgb/0.2" in client.out
    assert "pkgb/0.1" not in client.out
    assert "pkgd/0.1: DEP FILE PkgJ: HelloJ" in client.out
    assert "pkgd/0.1: DEP FILE pkgb: ByeB World!!" in client.out

    pkgd2_lockfile = client.load("pkgd2.lock")
    print(pkgd2_lockfile)
    assert "pkgb/0.2" in pkgd2_lockfile
    assert "pkgb/0.1" not in pkgd2_lockfile


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
