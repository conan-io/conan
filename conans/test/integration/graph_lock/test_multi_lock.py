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
    client.run("lock create --ref=app1/0.1 -s os=Linux  --lockfile=app1_base.lock "
               "--lockfile-out=app1_linux.lock")
    client.run("lock create --ref=app2/0.1 -s os=Windows  --lockfile=app2_base.lock "
               "--lockfile-out=app2_windows.lock")
    client.run("lock create --ref=app2/0.1 -s os=Linux  --lockfile=app2_base.lock "
               "--lockfile-out=app2_linux.lock")

    client.run("lock multi --lockfile=app1_windows.lock --lockfile=app1_linux.lock "
               "--lockfile=app2_windows.lock --lockfile=app2_linux.lock --lockfile-out=multi.lock")

    client.run("lock build-order-multi multi.lock --json=bo.json")
    order = client.load("bo.json")
    order = json.loads(order)
    assert order == [
        ["pkga/0.1@#f096d7d54098b7ad7012f9435d9c33f3"],
        ["pkgb/0.1@#cd8f22d6f264f65398d8c534046e8e20", "pkgb/0.2@#cd8f22d6f264f65398d8c534046e8e20"],
        ["app1/0.1@#584778f98ba1d0eb7c80a5ae1fe12fe2", "app2/0.1@#3850895c1eac8223c43c71d525348019"]
    ]
    multi = client.load("multi.lock")
    multi = json.loads(multi)
    for level in order:
        for ref in level:
            # Now get the package_id, lockfile
            pkg_ids = multi[ref]["package_id"]
            for pkg_id, lockfile_info in pkg_ids.items():
                lockfiles = lockfile_info["lockfiles"]
                lockfile = next(iter(lockfiles))
                client.run("install {ref} --build={ref} --lockfile={lockfile} "
                           "--lockfile-out={lockfile}".format(ref=ref, lockfile=lockfile))
                client.run("lock update-multi multi.lock")

    app1_win = GraphLockFile.load(os.path.join(client.current_folder, "app1_windows.lock"),
                                  client.cache.config.revisions_enabled)
    nodes = app1_win.graph_lock.nodes
    assert nodes["1"].modified is True
    assert nodes["1"].ref.full_str() == "app1/0.1#584778f98ba1d0eb7c80a5ae1fe12fe2"
    assert nodes["1"].prev == "c6658a5c66393cf4d210c35b5fbf34f8"

    assert nodes["2"].modified is True
    assert nodes["2"].ref.full_str() == "pkgb/0.1#cd8f22d6f264f65398d8c534046e8e20"
    assert nodes["2"].prev == "615cacb4d607885967a627eab1d1069d"

    assert nodes["3"].modified is True
    assert nodes["3"].ref.full_str() == "pkga/0.1#f096d7d54098b7ad7012f9435d9c33f3"
    assert nodes["3"].prev == "d0f0357277b3417d3984b5a9a85bbab6"

    app2_win = GraphLockFile.load(os.path.join(client.current_folder, "app2_linux.lock"),
                                  client.cache.config.revisions_enabled)
    nodes = app2_win.graph_lock.nodes
    assert nodes["1"].modified is True
    assert nodes["1"].ref.full_str() == "app2/0.1#3850895c1eac8223c43c71d525348019"
    assert nodes["1"].prev == "f1ca88c668b7f573037d09cb04be0e6f"

    assert nodes["2"].modified is True
    assert nodes["2"].ref.full_str() == "pkgb/0.2#cd8f22d6f264f65398d8c534046e8e20"
    assert nodes["2"].prev == "615cacb4d607885967a627eab1d1069d"

    assert nodes["3"].modified is True
    assert nodes["3"].ref.full_str() == "pkga/0.1#f096d7d54098b7ad7012f9435d9c33f3"
    assert nodes["3"].prev == "9e99cfd92d0d7df79d687b01512ce844"


