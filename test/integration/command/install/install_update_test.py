import json
import os
import textwrap
from time import sleep

from conan.api.model import RecipeReference
from conan.test.utils.tools import TestClient, GenConanfile, TestServer
from conan.internal.util.files import load


def test_update_binaries():
    client = TestClient(default_server_user=True)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save, load
        import os, random
        class Pkg(ConanFile):
            def package(self):
                save(self, os.path.join(self.package_folder, "file.txt"), str(random.random()))

            def package_info(self):
                content = load(self, os.path.join(self.package_folder, "file.txt"))
                self.output.warning("CONTENT=>{}#".format(content))

        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")
    client.run("upload pkg/0.1@lasote/testing -r default")

    client2 = TestClient(servers=client.servers, inputs=["admin", "password"])
    client2.run("install --requires=pkg/0.1@lasote/testing")

    def get_value_from_output(output):
        tmp = str(output).split("CONTENT=>")[1]
        return tmp.split("#")[0]

    value = get_value_from_output(client2.out)

    client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")  # Because of random, this should be NEW prev
    client.run("upload pkg/0.1@lasote/testing -r default")

    client2.run("install --requires=pkg/0.1@lasote/testing")
    new_value = get_value_from_output(client2.out)
    assert value == new_value

    client2.run("install --requires=pkg/0.1@lasote/testing --update")
    assert "Current package revision is older than the remote one" in client2.out
    new_value = get_value_from_output(client2.out)
    assert value != new_value

    # Now check newer local modifications are not overwritten
    client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")
    client.run("upload pkg/0.1@lasote/testing -r default")

    client2.save({"conanfile.py": conanfile})
    client2.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")
    client2.run("install --requires=pkg/0.1@lasote/testing")
    value2 = get_value_from_output(client2.out)
    client2.run("install --requires=pkg/0.1@lasote/testing --update -r default")
    assert "Current package revision is newer than the remote one" in client2.out
    new_value = get_value_from_output(client2.out)
    assert value2 == new_value


def test_update_not_date():
    client = TestClient(default_server_user=True)
    # Regression for https://github.com/conan-io/conan/issues/949
    client.save({"conanfile.py": GenConanfile("hello0", "1.0")})
    client.run("export . --user=lasote --channel=stable")
    client.save({"conanfile.py": GenConanfile("hello1", "1.0").
                with_requirement("hello0/1.0@lasote/stable")},
                clean_first=True)
    client.run("install . --build='*'")
    client.run("upload hello0/1.0@lasote/stable -r default")

    prev = client.get_latest_package_reference("hello0/1.0@lasote/stable")

    ref = RecipeReference.loads("hello0/1.0@lasote/stable")

    initial_recipe_timestamp = client.cache.get_latest_recipe_revision(ref).timestamp
    initial_package_timestamp = prev.timestamp

    # Change and rebuild package
    client.save({"conanfile.py": GenConanfile("hello0", "1.0").with_class_attribute("author = 'O'")},
                clean_first=True)
    client.run("export . --user=lasote --channel=stable")
    client.run("install --requires=hello0/1.0@lasote/stable --build='*'")

    rebuild_recipe_timestamp = client.cache.get_latest_recipe_revision(ref).timestamp
    rebuild_package_timestamp = client.get_latest_package_reference(ref).timestamp

    assert rebuild_recipe_timestamp != initial_recipe_timestamp
    assert rebuild_package_timestamp != initial_package_timestamp

    # back to the consumer, try to update
    client.save({"conanfile.py": GenConanfile("hello1", "1.0").
                with_requirement("hello0/1.0@lasote/stable")}, clean_first=True)
    # First assign the preference to a remote, it has been cleared when exported locally
    client.run("install . --update")
    # *1 With revisions here is removing the package because it doesn't belong to the recipe

    client.assert_listed_require({"hello0/1.0@lasote/stable": "Newer"})

    failed_update_recipe_timestamp = client.cache.get_latest_recipe_revision(ref).timestamp
    failed_update_package_timestamp = client.get_latest_package_reference(ref).timestamp

    assert rebuild_recipe_timestamp == failed_update_recipe_timestamp
    assert rebuild_package_timestamp == failed_update_package_timestamp


def test_reuse():
    client = TestClient(default_server_user=True)
    conanfile = GenConanfile("hello0", "1.0")\
        .with_exports_sources("*")\
        .with_import("from conan.tools.files import copy")\
        .with_package("copy(self, '*', self.source_folder, self.package_folder)")
    client.save({"conanfile.py": conanfile,
                 "header.h": "content1"})
    client.run("export . --user=lasote --channel=stable")
    client.run("install --requires=hello0/1.0@lasote/stable --build='*'")
    client.run("upload hello0/1.0@lasote/stable -r default")

    client2 = TestClient(servers=client.servers, inputs=["admin", "password"])
    client2.run("install --requires=hello0/1.0@lasote/stable")
    assert "hello0/1.0@lasote/stable: Retrieving package" in client2.out

    client.save({"header.h": "//EMPTY!"})
    sleep(1)
    client.run("export . --user=lasote --channel=stable")
    client.run("install --requires=hello0/1.0@lasote/stable --build='*'")
    client.run("upload hello0/1.0@lasote/stable -r default")

    client2.run("install --requires=hello0/1.0@lasote/stable --update")
    ref = RecipeReference.loads("hello0/1.0@lasote/stable")
    pref = client.get_latest_package_reference(ref)
    package_path = client2.get_latest_pkg_layout(pref).package()
    header = load(os.path.join(package_path, "header.h"))
    assert header == "//EMPTY!"


def test_update_binaries_failed():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")
    client.run("install --requires=pkg/0.1@lasote/testing --update")
    assert "WARN: Can't update, there are no remotes defined" in client.out


def test_install_update_repeated_tool_requires():
    """
    Test that requiring the same thing multiple times, like a tool-requires, only
    require checking the servers 1, so it is much faster

    https://github.com/conan-io/conan/issues/13508
    """
    c = TestClient(default_server_user=True)
    c.save({"tool/conanfile.py": GenConanfile("tool", "0.1"),
            "liba/conanfile.py": GenConanfile("liba", "0.1"),
            "libb/conanfile.py": GenConanfile("libb", "0.1").with_requires("liba/0.1"),
            "libc/conanfile.py": GenConanfile("libc", "0.1").with_requires("libb/0.1"),
            "profile": "[tool_requires]\ntool/0.1"
            })
    c.run("create tool")
    c.run("create liba")
    c.run("create libb")
    c.run("create libc")
    c.run("install libc --update -pr=profile")
    assert 1 == str(c.out).count("tool/0.1: Checking remote")


class TestUpdateOldPolicy:
    def test_multi_remote_update_resolution(self):
        c = TestClient(servers={"r1": TestServer(), "r2": TestServer(), "r3": TestServer()},
                       inputs=["admin", "password"] * 3, light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c.run("export .")
        rev1 = c.exported_recipe_revision()
        c.run("upload * -r=r1 -c")
        # second revision
        c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_class_attribute("auther = 'me'")})
        c.run("export .")
        rev2 = c.exported_recipe_revision()
        assert rev1 != rev2
        c.run("upload * -r=r2 -c")  # By default uploads latest revisions only
        assert rev1 not in c.out
        assert rev2 in c.out
        # going back to the previous revision
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c.run("export .")  # Makes it the latest
        rev3 = c.exported_recipe_revision()
        assert rev1 == rev3
        c.run("upload * -r=r3 -c")  # By default uploads latest revisions only
        assert rev3 in c.out
        assert rev2 not in c.out

        # now test the --update, it will pick up the latest revision, which is r3
        c.run("remove * -c")
        c.run("graph info --requires=pkg/0.1 --update")
        assert f"pkg/0.1#{rev3} - Downloaded (r3)" in c.out

        # But if we enable order-based first found timestamp, it will pick up r2
        c.run("remove * -c")
        c.run("graph info --requires=pkg/0.1 --update -cc core:update_policy=legacy")
        assert "The 'core:update_policy' conf is deprecated and will be removed" in c.out
        assert f"pkg/0.1#{rev2} - Downloaded (r2)" in c.out

    def test_multi_remote_update_resolution_2_remotes(self):
        c = TestClient(servers={"r1": TestServer(), "r2": TestServer()},
                       inputs=["admin", "password"] * 2, light=True)
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c.run("export .")
        rev1 = c.exported_recipe_revision()
        c.run("upload * -r=r1 -c")
        # second revision
        c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_class_attribute("auther = 'me'")})
        c.run("export .")
        rev2 = c.exported_recipe_revision()
        assert rev1 != rev2
        c.run("upload * -r=r1 -c")
        c.run("list *#* -r=r1")

        # Upload the first, old revision to the other remote
        c.run(f"upload pkg/0.1#{rev1} -r=r2 -c")
        assert rev1 in c.out
        assert rev2 not in c.out
        c.run("list *#* -r=r2")

        # now test the --update, it will pick up the latest revision, which is r3
        c.run("remove * -c")
        c.run("graph info --requires=pkg/0.1 --update")
        assert f"pkg/0.1#{rev1} - Downloaded (r2)" in c.out

        # But if we enable order-based first found timestamp, it will pick up r2
        c.run("remove * -c")
        c.run("graph info --requires=pkg/0.1 --update -cc core:update_policy=legacy")
        assert f"pkg/0.1#{rev2} - Downloaded (r1)" in c.out

    def test_lockfile(self):
        # https://github.com/conan-io/conan/issues/18006
        c = TestClient(default_server_user=True, light=True)  # needs server to fail
        c.save_home({"global.conf": "core:update_policy=legacy"})
        c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
                "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_python_requires("dep/0.1")})
        c.run("create dep")
        c.run("lock create pkg --lockfile-out base.lock --build=* --update")
        c.run("lock create pkg --lockfile base.lock --lockfile-out full.lock --build=* --update")
        # it doesn't crash
        assert "Generated lockfile" in c.out


def test_update_remote_not_latest_in_cache():
    """
    rrev1 is present in the remote and in the cache, but then we create a new rev locally,
    if we now try to install using --update, the newer local cache one should be used,
    not the remote one which is older
    """
    tc = TestClient(default_server_user=True, light=True)
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    import time
    import os

    class Pkg(ConanFile):
        name = "pkg"
        version = "0.1"

        def package(self):
            with open(os.path.join(self.package_folder, "file.txt"), "w") as f:
                f.write(str(time.time()))
    """)
    # Different revisions for the same recipe
    tc.save({"rrev1/conanfile.py": GenConanfile("pkg", "0.1"),
             "rrev2/conanfile.py": conanfile})
    tc.run("create rrev1")
    rrev1 = tc.exported_recipe_revision()
    tc.run("upload pkg/0.1 -r=default -c")

    tc.run("create rrev2")
    old_rrev2_layout = tc.created_layout()
    rrev2 = old_rrev2_layout.reference.ref.revision
    tc.run("install --requires=pkg/0.1 --update")
    assert rrev1 not in tc.out
    assert rrev2 in tc.out

    tc.run("upload pkg/0.1 -r=default -c")
    tc.run("list pkg/0.1#latest:*#latest -r=default")
    assert rrev2 in tc.out
    assert old_rrev2_layout.reference.revision in tc.out

    # Now with package revisions, the behavior is the same
    tc.run("create rrev2")
    new_rrev2_layout = tc.created_layout()
    assert old_rrev2_layout.reference.ref.revision == new_rrev2_layout.reference.ref.revision
    assert old_rrev2_layout.reference.revision != new_rrev2_layout.reference.revision

    tc.run("install --requires=pkg/0.1 --update")
    tc.assert_listed_binary({str(new_rrev2_layout.reference.ref): (new_rrev2_layout.reference.package_id, "Cache")})


def test_package_revision_timestamp_mismatch():
    """
    Updating from a remote whose latest prev is older than the local newer one failed
    if the remote's prev was also present in the local cache
    see https://github.com/conan-io/conan/issues/20333
    """
    tc = TestClient(default_server_user=True, light=True)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        import time
        import os

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def package(self):
                with open(os.path.join(self.package_folder, "file.txt"), "w") as f:
                    f.write(str(time.time()))
        """)
    tc.save({"conanfile.py": conanfile})
    tc.run("create")
    old_layout = tc.created_layout()

    tc.run("create")
    new_layout = tc.created_layout()
    assert old_layout.reference.revision != new_layout.reference.revision

    tc.run("list pkg/0.1#latest:*#latest -f=json", redirect_stdout="local.json")
    local_list = json.loads(tc.load("local.json"))
    local_timestamp = local_list["Local Cache"]["pkg/0.1"]["revisions"][new_layout.reference.ref.revision]["packages"][new_layout.reference.package_id]["revisions"][new_layout.reference.revision]["timestamp"]

    # We're uploading the old package revision, which locally has an older timestamp than the new one,
    # but not remotely
    tc.run(f"upload {old_layout.reference.repr_notime()} -r=default -c")
    assert f"{old_layout.reference.revision} (Uploaded)" in tc.out

    tc.run("list pkg/0.1#latest:*#latest -r=default -f=json", redirect_stdout="remote.json")
    remote_json = json.loads(tc.load("remote.json"))
    remote_timestamp = remote_json["default"]["pkg/0.1"]["revisions"][old_layout.reference.ref.revision]["packages"][old_layout.reference.package_id]["revisions"][old_layout.reference.revision]["timestamp"]
    # Note that the local latest prev has an older timestamp than the remote's,
    # as the remote updates the timestamp when uploading
    assert remote_timestamp > local_timestamp

    # This currently fails
    tc.run("install --requires=pkg/0.1 --update")
    assert old_layout.reference.revision in tc.out
    assert new_layout.reference.revision not in tc.out
