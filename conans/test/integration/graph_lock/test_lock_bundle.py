import json
import os

from conans.model.graph_lock import GraphLockFile
from conans.test.utils.tools import TestClient, GenConanfile


def test_basic():
    client = TestClient()
    # TODO: This is hardcoded
    client.run("config set general.revisions_enabled=1")
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
            packages = bundle[ref]["packages"]
            for pkg in packages:
                lockfiles = pkg["lockfiles"]
                lockfile = next(iter(sorted(lockfiles)))

                client.run("install {ref} --build={ref} --lockfile={lockfile} "
                           "--lockfile-out={lockfile}".format(ref=ref, lockfile=lockfile))
                client.run("lock bundle update lock1.bundle")

    app1_win = GraphLockFile.load(os.path.join(client.current_folder, "app1_windows.lock"),
                                  client.cache.config.revisions_enabled)
    nodes = app1_win.graph_lock.nodes
    assert nodes["1"].modified is True
    assert nodes["1"].ref.full_str() == "app1/0.1#584778f98ba1d0eb7c80a5ae1fe12fe2"
    assert nodes["1"].package_id == "3bcd6800847f779e0883ee91b411aad9ddd8e83c"
    assert nodes["1"].prev == "c6658a5c66393cf4d210c35b5fbf34f8"

    assert nodes["2"].modified is True
    assert nodes["2"].ref.full_str() == "pkgb/0.1#cd8f22d6f264f65398d8c534046e8e20"
    assert nodes["2"].package_id == "cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23"
    assert nodes["2"].prev == "d61b9f421cada3b4d8e39540b0aea3d0"

    assert nodes["3"].modified is True
    assert nodes["3"].ref.full_str() == "pkga/0.1#f096d7d54098b7ad7012f9435d9c33f3"
    assert nodes["3"].package_id == "3475bd55b91ae904ac96fde0f106a136ab951a5e"
    assert nodes["3"].prev == "d0f0357277b3417d3984b5a9a85bbab6"

    app2_linux = GraphLockFile.load(os.path.join(client.current_folder, "app2_linux.lock"),
                                    client.cache.config.revisions_enabled)
    nodes = app2_linux.graph_lock.nodes
    assert nodes["1"].modified is True
    assert nodes["1"].ref.full_str() == "app2/0.1#3850895c1eac8223c43c71d525348019"
    assert nodes["1"].package_id == "156f38906bdcdceba1b26a206240cf199619fee1"
    assert nodes["1"].prev == "f1ca88c668b7f573037d09cb04be0e6f"

    assert nodes["2"].modified is True
    assert nodes["2"].ref.full_str() == "pkgb/0.2#cd8f22d6f264f65398d8c534046e8e20"
    assert nodes["2"].package_id == "cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23"
    assert nodes["2"].prev == "d61b9f421cada3b4d8e39540b0aea3d0"

    assert nodes["3"].modified is True
    assert nodes["3"].ref.full_str() == "pkga/0.1#f096d7d54098b7ad7012f9435d9c33f3"
    assert nodes["3"].package_id == "cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31"
    assert nodes["3"].prev == "9e99cfd92d0d7df79d687b01512ce844"

    client.run("lock bundle clean-modified lock1.bundle")
    bundle = client.load("lock1.bundle")
    assert '"modified": true' not in bundle
    lock1 = client.load("app1_windows.lock")
    assert '"modified": true' not in lock1
    lock2 = client.load("app2_linux.lock")
    assert '"modified": true' not in lock2


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
            packages = bundle[ref]["packages"]
            for pkg in packages:
                lockfiles = pkg["lockfiles"]
                lockfile = next(iter(sorted(lockfiles)))

                client.run("install {ref} --build={ref} --lockfile={lockfile} "
                           "--lockfile-out={lockfile}".format(ref=ref, lockfile=lockfile))
                client.run("lock bundle update lock1.bundle")

    app1_win = GraphLockFile.load(os.path.join(client.current_folder, "app1_windows.lock"),
                                  client.cache.config.revisions_enabled)
    nodes = app1_win.graph_lock.nodes
    assert nodes["1"].modified is True
    assert nodes["1"].ref.full_str() == "app1/0.1#584778f98ba1d0eb7c80a5ae1fe12fe2"
    assert nodes["1"].package_id == "3bcd6800847f779e0883ee91b411aad9ddd8e83c"
    assert nodes["1"].prev == "c6658a5c66393cf4d210c35b5fbf34f8"

    assert nodes["2"].modified is True
    assert nodes["2"].ref.full_str() == "pkgb/0.1#cd8f22d6f264f65398d8c534046e8e20"
    assert nodes["2"].package_id == "cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23"
    assert nodes["2"].prev == "d61b9f421cada3b4d8e39540b0aea3d0"

    assert nodes["3"].modified is True
    assert nodes["3"].ref.full_str() == "pkga/0.1#f096d7d54098b7ad7012f9435d9c33f3"
    assert nodes["3"].package_id == "3475bd55b91ae904ac96fde0f106a136ab951a5e"
    assert nodes["3"].prev == "d0f0357277b3417d3984b5a9a85bbab6"

    for n in ("5", "6", "7"):
        assert nodes[n].modified is True
        assert nodes[n].ref.full_str() == "tool/0.1#f096d7d54098b7ad7012f9435d9c33f3"
        assert nodes[n].package_id == "3475bd55b91ae904ac96fde0f106a136ab951a5e"
        assert nodes[n].prev == "d0f0357277b3417d3984b5a9a85bbab6"

    app2_linux = GraphLockFile.load(os.path.join(client.current_folder, "app2_linux.lock"),
                                    client.cache.config.revisions_enabled)
    nodes = app2_linux.graph_lock.nodes
    assert nodes["1"].modified is True
    assert nodes["1"].ref.full_str() == "app2/0.1#3850895c1eac8223c43c71d525348019"
    assert nodes["1"].package_id == "156f38906bdcdceba1b26a206240cf199619fee1"
    assert nodes["1"].prev == "f1ca88c668b7f573037d09cb04be0e6f"

    assert nodes["2"].modified is True
    assert nodes["2"].ref.full_str() == "pkgb/0.2#cd8f22d6f264f65398d8c534046e8e20"
    assert nodes["2"].package_id == "cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23"
    assert nodes["2"].prev == "d61b9f421cada3b4d8e39540b0aea3d0"

    assert nodes["3"].modified is True
    assert nodes["3"].ref.full_str() == "pkga/0.1#f096d7d54098b7ad7012f9435d9c33f3"
    assert nodes["3"].package_id == "cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31"
    assert nodes["3"].prev == "9e99cfd92d0d7df79d687b01512ce844"

    for n in ("5", "6", "7"):
        assert nodes[n].modified is True
        assert nodes[n].ref.full_str() == "tool/0.1#f096d7d54098b7ad7012f9435d9c33f3"
        assert nodes[n].package_id == "cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31"
        assert nodes[n].prev == "9e99cfd92d0d7df79d687b01512ce844"


def test_build_requires_error():
    # https://github.com/conan-io/conan/issues/8577
    client = TestClient()
    # TODO: This is hardcoded
    client.run("config set general.revisions_enabled=1")
    client.save({"tool/conanfile.py": GenConanfile().with_settings("os"),
                 "pkga/conanfile.py": GenConanfile().with_settings("os"),
                 "app1/conanfile.py": GenConanfile().with_settings("os").with_requires("pkga/0.1"),
                 "profile": "[build_requires]\ntool/0.1"})
    client.run("create tool tool/0.1@ -s os=Windows")
    client.run("create tool tool/0.1@ -s os=Linux")
    client.run("export pkga pkga/0.1@")
    client.run("export app1 app1/0.1@")

    client.run("lock create --ref=app1/0.1 -pr=profile -s os=Windows "
               "--lockfile-out=app1_windows.lock --build=missing")
    assert "tool/0.1:3475bd55b91ae904ac96fde0f106a136ab951a5e - Cache" in client.out
    client.run("lock create --ref=app1/0.1 -pr=profile -s os=Linux "
               "--lockfile-out=app1_linux.lock --build=missing")
    assert "tool/0.1:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31 - Cache" in client.out

    client.run("lock bundle create app1_windows.lock app1_linux.lock --bundle-out=lock1.bundle")
    client.run("lock bundle build-order lock1.bundle --json=bo.json")
    order = client.load("bo.json")
    print(order)
    order = json.loads(order)
    assert order == [
        ["pkga/0.1@#f096d7d54098b7ad7012f9435d9c33f3"],
        ["app1/0.1@#5af607abc205b47375f485a98abc3b38"]
    ]
