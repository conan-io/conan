import os
import textwrap
import time
from time import sleep

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient, GenConanfile
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
    client2.run("install --reference=pkg/0.1@lasote/testing")

    def get_value_from_output(output):
        tmp = str(output).split("CONTENT=>")[1]
        return tmp.split("#")[0]

    value = get_value_from_output(client2.out)

    time.sleep(1)  # Make sure the new timestamp is later
    client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")  # Because of random, this should be NEW prev
    client.run("upload pkg/0.1@lasote/testing -r default")

    client2.run("install --reference=pkg/0.1@lasote/testing")
    new_value = get_value_from_output(client2.out)
    assert value == new_value

    client2.run("install --reference=pkg/0.1@lasote/testing --update")
    assert "Current package revision is older than the remote one" in client2.out
    new_value = get_value_from_output(client2.out)
    assert value != new_value

    # Now check newer local modifications are not overwritten
    time.sleep(1)  # Make sure the new timestamp is later
    client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")
    client.run("upload pkg/0.1@lasote/testing -r default")

    client2.save({"conanfile.py": conanfile})
    client2.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")
    client2.run("install --reference=pkg/0.1@lasote/testing")
    value2 = get_value_from_output(client2.out)
    client2.run("install --reference=pkg/0.1@lasote/testing --update -r default")
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
    client.run("install . --build")
    client.run("upload hello0/1.0@lasote/stable -r default")

    prev = client.get_latest_package_reference("hello0/1.0@lasote/stable")

    ref = RecipeReference.loads("hello0/1.0@lasote/stable")

    initial_recipe_timestamp = client.cache.get_recipe_timestamp(client.cache.get_latest_recipe_reference(ref))
    initial_package_timestamp = client.cache.get_package_timestamp(prev)

    time.sleep(1)

    # Change and rebuild package
    client.save({"conanfile.py": GenConanfile("hello0", "1.0").with_class_attribute("author = 'O'")},
                clean_first=True)
    client.run("export . --user=lasote --channel=stable")
    client.run("install --reference=hello0/1.0@lasote/stable --build")

    rebuild_recipe_timestamp = client.cache.get_recipe_timestamp(client.cache.get_latest_recipe_reference(ref))
    rebuild_package_timestamp = client.cache.get_package_timestamp(client.get_latest_package_reference(ref))

    assert rebuild_recipe_timestamp != initial_recipe_timestamp
    assert rebuild_package_timestamp != initial_package_timestamp

    # back to the consumer, try to update
    client.save({"conanfile.py": GenConanfile("hello1", "1.0").
                with_requirement("hello0/1.0@lasote/stable")}, clean_first=True)
    # First assign the preference to a remote, it has been cleared when exported locally
    client.run("install . --update")
    # *1 With revisions here is removing the package because it doesn't belong to the recipe

    client.assert_listed_require({"hello0/1.0@lasote/stable": "Newer"})

    failed_update_recipe_timestamp = client.cache.get_recipe_timestamp(client.cache.get_latest_recipe_reference(ref))
    failed_update_package_timestamp = client.cache.get_package_timestamp(client.get_latest_package_reference(ref))

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
    client.run("install --reference=hello0/1.0@lasote/stable --build")
    client.run("upload hello0/1.0@lasote/stable -r default")

    client2 = TestClient(servers=client.servers, inputs=["admin", "password"])
    client2.run("install --reference=hello0/1.0@lasote/stable")

    assert str(client2.out).count("Downloading conaninfo.txt") == 1

    client.save({"header.h": "//EMPTY!"})
    sleep(1)
    client.run("export . --user=lasote --channel=stable")
    client.run("install --reference=hello0/1.0@lasote/stable --build")
    client.run("upload hello0/1.0@lasote/stable -r default")

    client2.run("install --reference=hello0/1.0@lasote/stable --update")
    ref = RecipeReference.loads("hello0/1.0@lasote/stable")
    pref = client.get_latest_package_reference(ref)
    package_path = client2.get_latest_pkg_layout(pref).package()
    header = load(os.path.join(package_path, "header.h"))
    assert header == "//EMPTY!"


def test_update_binaries_failed():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")
    client.run("install --reference=pkg/0.1@lasote/testing --update")
    assert "pkg/0.1@lasote/testing: WARN: Can't update, there are no remotes configured or " \
           "enabled" in client.out
