import json

from conans.test.utils.tools import TestClient, GenConanfile


def test_basic():
    client = TestClient()
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
    # print(client.load("app1_base.lock"))
    client.run("lock create --ref=app1/0.1 -s os=Windows --lockfile-out=app1_windows.lock")
    # print(client.load("app1_windows.lock"))
    client.run("lock create --ref=app1/0.1 -s os=Linux --lockfile-out=app1_linux.lock")

    client.run("lock create --ref=app2/0.1 -s os=Windows --lockfile-out=app2_windows.lock")
    client.run("lock create --ref=app2/0.1 -s os=Linux --lockfile-out=app2_linux.lock")

    client.run("lock multi --lockfile=app1_windows.lock --lockfile=app1_linux.lock "
               "--lockfile=app2_windows.lock --lockfile=app2_linux.lock --lockfile-out=multi.lock")
    print(client.load("multi.lock"))

    client.run("lock build-order multi.lock --multi --json=bo.json")
    order = client.load("bo.json")
    multi = client.load("multi.lock")
    print(order)
    order = json.loads(order)
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
