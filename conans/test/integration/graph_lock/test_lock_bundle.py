import json
import os

from conans.model.graph_lock import GraphLockFile
from conans.test.utils.tools import TestClient, GenConanfile


def test_basic():
    client = TestClient()
    client.save({"pkga/conanfile.py": GenConanfile().with_settings("os"),
                 "pkgb/conanfile.py": GenConanfile().with_requires("pkga/0.1"),
                 "app1/conanfile.py": GenConanfile().with_settings("os").with_requires("pkgb/0.1"),
                 "app2/conanfile.py": GenConanfile().with_settings("os").with_requires("pkgb/0.2")})
    client.run("export pkga pkga/0.1@")
    client.run("export pkgb pkgb/0.1@")
    client.run("export pkgb pkgb/0.2@")
    client.run("export app1 app1/0.1@")
    client.run("export app2 app2/0.1@")
    client.run("lock create --ref=app1/0.1 --base --lockfile-out=app1_base.lock")
    client.run("lock create --ref=app2/0.1 --base --lockfile-out=app2_base.lock")

    client.run("lock create --ref=app1/0.1 -s os=Windows --lockfile=app1_base.lock "
               "--lockfile-out=app1_windows.lock")
    assert "app1/0.1:3bcd6800847f779e0883ee91b411aad9ddd8e83c - Missing" in client.out
    assert "pkga/0.1:3475bd55b91ae904ac96fde0f106a136ab951a5e - Missing" in client.out
    assert "pkgb/0.1:cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23 - Missing" in client.out
    client.run("lock create --ref=app1/0.1 -s os=Linux  --lockfile=app1_base.lock "
               "--lockfile-out=app1_linux.lock")
    assert "app1/0.1:60fbb0a22359b4888f7ecad69bcdfcd6e70e2784 - Missing" in client.out
    assert "pkga/0.1:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31 - Missing" in client.out
    assert "pkgb/0.1:cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23 - Missing" in client.out
    client.run("lock create --ref=app2/0.1 -s os=Windows  --lockfile=app2_base.lock "
               "--lockfile-out=app2_windows.lock")
    assert "app2/0.1:0f886d82040d47739aa363db84eef5fe4c958c23 - Missing" in client.out
    assert "pkga/0.1:3475bd55b91ae904ac96fde0f106a136ab951a5e - Missing" in client.out
    assert "pkgb/0.2:cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23 - Missing" in client.out
    client.run("lock create --ref=app2/0.1 -s os=Linux  --lockfile=app2_base.lock "
               "--lockfile-out=app2_linux.lock")
    assert "app2/0.1:156f38906bdcdceba1b26a206240cf199619fee1 - Missing" in client.out
    assert "pkga/0.1:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31 - Missing" in client.out
    assert "pkgb/0.2:cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23 - Missing" in client.out

    client.run("lock bundle create app1_windows.lock app1_linux.lock "
               "app2_windows.lock app2_linux.lock --bundle-out=lock1.bundle")

    client.run("lock bundle build-order lock1.bundle --json=bo.json")
    order = client.load("bo.json")
    order = json.loads(order)
    assert order == [
        ["pkga/0.1@#f096d7d54098b7ad7012f9435d9c33f3"],
        ["pkgb/0.1@#cd8f22d6f264f65398d8c534046e8e20", "pkgb/0.2@#cd8f22d6f264f65398d8c534046e8e20"],
        ["app1/0.1@#584778f98ba1d0eb7c80a5ae1fe12fe2", "app2/0.1@#3850895c1eac8223c43c71d525348019"]
    ]
    bundle = client.load("lock1.bundle")
    bundle = json.loads(bundle)["lock_bundle"]
    for level in order:
        for ref in level:
            # Now get the package_id, lockfile
            pkg_ids = bundle[ref]["package_id"]
            for pkg_id, lockfile_info in pkg_ids.items():
                lockfiles = lockfile_info["lockfiles"]
                lockfile = next(iter(sorted(lockfiles)))

                client.run("install {ref} --build={ref} --lockfile={lockfile} "
                           "--lockfile-out={lockfile}".format(ref=ref, lockfile=lockfile))
                client.run("lock bundle update lock1.bundle")

    app1_win = GraphLockFile.load(os.path.join(client.current_folder, "app1_windows.lock"))
    nodes = app1_win.graph_lock.nodes
    assert nodes["1"].modified is True
    assert nodes["1"].ref.full_str() == "app1/0.1#584778f98ba1d0eb7c80a5ae1fe12fe2"
    assert nodes["1"].package_id == "3bcd6800847f779e0883ee91b411aad9ddd8e83c"
    assert nodes["1"].prev == "ca93f8a2b7cfa755e3f769f230d3de08"

    assert nodes["2"].modified is True
    assert nodes["2"].ref.full_str() == "pkgb/0.1#cd8f22d6f264f65398d8c534046e8e20"
    assert nodes["2"].package_id == "cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23"
    assert nodes["2"].prev == "bc71ad422e9e49cf476dac6a7faa384a"

    assert nodes["3"].modified is True
    assert nodes["3"].ref.full_str() == "pkga/0.1#f096d7d54098b7ad7012f9435d9c33f3"
    assert nodes["3"].package_id == "3475bd55b91ae904ac96fde0f106a136ab951a5e"
    assert nodes["3"].prev == "0f2ac617ecf857a183b812307b2902c1"

    app2_linux = GraphLockFile.load(os.path.join(client.current_folder, "app2_linux.lock"))
    nodes = app2_linux.graph_lock.nodes
    assert nodes["1"].modified is True
    assert nodes["1"].ref.full_str() == "app2/0.1#3850895c1eac8223c43c71d525348019"
    assert nodes["1"].package_id == "156f38906bdcdceba1b26a206240cf199619fee1"
    assert nodes["1"].prev == "721c60fe5a1da4268781bc3a61d103ed"

    assert nodes["2"].modified is True
    assert nodes["2"].ref.full_str() == "pkgb/0.2#cd8f22d6f264f65398d8c534046e8e20"
    assert nodes["2"].package_id == "cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23"
    assert nodes["2"].prev == "bc71ad422e9e49cf476dac6a7faa384a"

    assert nodes["3"].modified is True
    assert nodes["3"].ref.full_str() == "pkga/0.1#f096d7d54098b7ad7012f9435d9c33f3"
    assert nodes["3"].package_id == "cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31"
    assert nodes["3"].prev == "49a476d1af8fd693e5a5858c0a1e7813"


def test_build_requires():
    client = TestClient()
    # TODO: This is hardcoded
    client.run("config set general.revisions_enabled=1")
    client.save({"tool/conanfile.py": GenConanfile().with_settings("os"),
                 "pkga/conanfile.py": GenConanfile().with_settings("os"),
                 "pkgb/conanfile.py": GenConanfile().with_requires("pkga/0.1"),
                 "app1/conanfile.py": GenConanfile().with_settings("os").with_requires("pkgb/0.1"),
                 "app2/conanfile.py": GenConanfile().with_settings("os").with_requires("pkgb/0.2"),
                 "profile": "[build_requires]\ntool/0.1"})
    client.run("export tool tool/0.1@")
    client.run("export pkga pkga/0.1@")
    client.run("export pkgb pkgb/0.1@")
    client.run("export pkgb pkgb/0.2@")
    client.run("export app1 app1/0.1@")
    client.run("export app2 app2/0.1@")
    client.run("lock create --ref=app1/0.1 --base --lockfile-out=app1_base.lock")
    client.run("lock create --ref=app2/0.1 --base --lockfile-out=app2_base.lock")

    client.run("lock create --ref=app1/0.1 -pr=profile -s os=Windows --lockfile=app1_base.lock "
               "--lockfile-out=app1_windows.lock --build=missing")
    assert "tool/0.1:3475bd55b91ae904ac96fde0f106a136ab951a5e - Build" in client.out
    assert "app1/0.1:3bcd6800847f779e0883ee91b411aad9ddd8e83c - Build" in client.out
    assert "pkga/0.1:3475bd55b91ae904ac96fde0f106a136ab951a5e - Build" in client.out
    assert "pkgb/0.1:cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23 - Build" in client.out
    client.run("lock create --ref=app1/0.1 -pr=profile -s os=Linux  --lockfile=app1_base.lock "
               "--lockfile-out=app1_linux.lock --build=missing")
    assert "tool/0.1:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31 - Build" in client.out
    assert "app1/0.1:60fbb0a22359b4888f7ecad69bcdfcd6e70e2784 - Build" in client.out
    assert "pkga/0.1:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31 - Build" in client.out
    assert "pkgb/0.1:cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23 - Build" in client.out
    client.run("lock create --ref=app2/0.1 -pr=profile -s os=Windows  --lockfile=app2_base.lock "
               "--lockfile-out=app2_windows.lock --build=missing")
    assert "tool/0.1:3475bd55b91ae904ac96fde0f106a136ab951a5e - Build" in client.out
    assert "app2/0.1:0f886d82040d47739aa363db84eef5fe4c958c23 - Build" in client.out
    assert "pkga/0.1:3475bd55b91ae904ac96fde0f106a136ab951a5e - Build" in client.out
    assert "pkgb/0.2:cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23 - Build" in client.out
    client.run("lock create --ref=app2/0.1 -pr=profile -s os=Linux  --lockfile=app2_base.lock "
               "--lockfile-out=app2_linux.lock --build=missing")
    assert "tool/0.1:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31 - Build" in client.out
    assert "app2/0.1:156f38906bdcdceba1b26a206240cf199619fee1 - Build" in client.out
    assert "pkga/0.1:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31 - Build" in client.out
    assert "pkgb/0.2:cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23 - Build" in client.out

    client.run("lock bundle create app1_windows.lock app1_linux.lock "
               "app2_windows.lock app2_linux.lock --bundle-out=lock1.bundle")

    client.run("lock bundle build-order lock1.bundle --json=bo.json")
    order = client.load("bo.json")
    order = json.loads(order)
    assert order == [
        ["tool/0.1@#f096d7d54098b7ad7012f9435d9c33f3"],
        ["pkga/0.1@#f096d7d54098b7ad7012f9435d9c33f3"],
        ["pkgb/0.1@#cd8f22d6f264f65398d8c534046e8e20", "pkgb/0.2@#cd8f22d6f264f65398d8c534046e8e20"],
        ["app1/0.1@#584778f98ba1d0eb7c80a5ae1fe12fe2", "app2/0.1@#3850895c1eac8223c43c71d525348019"]
    ]
    bundle = client.load("lock1.bundle")
    print(bundle)
    bundle = json.loads(bundle)["lock_bundle"]
    for level in order:
        for ref in level:
            # Now get the package_id, lockfile
            pkg_ids = bundle[ref]["package_id"]
            for pkg_id, lockfile_info in pkg_ids.items():
                lockfiles = lockfile_info["lockfiles"]
                lockfile = next(iter(sorted(lockfiles)))

                client.run("install {ref} --build={ref} --lockfile={lockfile} "
                           "--lockfile-out={lockfile}".format(ref=ref, lockfile=lockfile))
                client.run("lock bundle update lock1.bundle")

    app1_win = GraphLockFile.load(os.path.join(client.current_folder, "app1_windows.lock"))
    nodes = app1_win.graph_lock.nodes
    assert nodes["1"].modified is True
    assert nodes["1"].ref.full_str() == "app1/0.1#584778f98ba1d0eb7c80a5ae1fe12fe2"
    assert nodes["1"].package_id == "3bcd6800847f779e0883ee91b411aad9ddd8e83c"
    assert nodes["1"].prev == "ca93f8a2b7cfa755e3f769f230d3de08"

    assert nodes["2"].modified is True
    assert nodes["2"].ref.full_str() == "pkgb/0.1#cd8f22d6f264f65398d8c534046e8e20"
    assert nodes["2"].package_id == "cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23"
    assert nodes["2"].prev == "bc71ad422e9e49cf476dac6a7faa384a"

    assert nodes["3"].modified is True
    assert nodes["3"].ref.full_str() == "pkga/0.1#f096d7d54098b7ad7012f9435d9c33f3"
    assert nodes["3"].package_id == "3475bd55b91ae904ac96fde0f106a136ab951a5e"
    assert nodes["3"].prev == "0f2ac617ecf857a183b812307b2902c1"

    for n in ("5", "6", "7"):
        assert nodes[n].modified is True
        assert nodes[n].ref.full_str() == "tool/0.1#f096d7d54098b7ad7012f9435d9c33f3"
        assert nodes[n].package_id == "3475bd55b91ae904ac96fde0f106a136ab951a5e"
        assert nodes[n].prev == "0f2ac617ecf857a183b812307b2902c1"

    app2_linux = GraphLockFile.load(os.path.join(client.current_folder, "app2_linux.lock"))
    nodes = app2_linux.graph_lock.nodes
    assert nodes["1"].modified is True
    assert nodes["1"].ref.full_str() == "app2/0.1#3850895c1eac8223c43c71d525348019"
    assert nodes["1"].package_id == "156f38906bdcdceba1b26a206240cf199619fee1"
    assert nodes["1"].prev == "721c60fe5a1da4268781bc3a61d103ed"

    assert nodes["2"].modified is True
    assert nodes["2"].ref.full_str() == "pkgb/0.2#cd8f22d6f264f65398d8c534046e8e20"
    assert nodes["2"].package_id == "cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23"
    assert nodes["2"].prev == "bc71ad422e9e49cf476dac6a7faa384a"

    assert nodes["3"].modified is True
    assert nodes["3"].ref.full_str() == "pkga/0.1#f096d7d54098b7ad7012f9435d9c33f3"
    assert nodes["3"].package_id == "cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31"
    assert nodes["3"].prev == "49a476d1af8fd693e5a5858c0a1e7813"

    for n in ("5", "6", "7"):
        assert nodes[n].modified is True
        assert nodes[n].ref.full_str() == "tool/0.1#f096d7d54098b7ad7012f9435d9c33f3"
        assert nodes[n].package_id == "cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31"
        assert nodes[n].prev == "49a476d1af8fd693e5a5858c0a1e7813"
