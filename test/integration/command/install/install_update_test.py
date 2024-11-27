import os
import textwrap
from time import sleep

from conans.model.recipe_ref import RecipeReference
from conan.test.utils.tools import TestClient, GenConanfile
from conans.util.files import load


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

    initial_recipe_timestamp = client.cache.get_latest_recipe_reference(ref).timestamp
    initial_package_timestamp = prev.timestamp

    # Change and rebuild package
    client.save({"conanfile.py": GenConanfile("hello0", "1.0").with_class_attribute("author = 'O'")},
                clean_first=True)
    client.run("export . --user=lasote --channel=stable")
    client.run("install --requires=hello0/1.0@lasote/stable --build='*'")

    rebuild_recipe_timestamp = client.cache.get_latest_recipe_reference(ref).timestamp
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

    failed_update_recipe_timestamp = client.cache.get_latest_recipe_reference(ref).timestamp
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
