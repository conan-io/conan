import re

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.env import environment_update


class TestUploadPatterns:
    @pytest.fixture(scope="class")  # Takes 6 seconds, reuse it
    def client(self):
        """ create a few packages, with several recipe revisions, several pids, several prevs
        """
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile().with_package_file("file", env_var="MYVAR")})

        for pkg in ("pkga", "pkgb"):
            for version in ("1.0", "1.1"):
                for rrev in ("rev1", "rev2"):
                    client.save({"conanfile.py": GenConanfile().with_settings("os")
                                .with_class_attribute(f"potato='{rrev}'")
                                .with_package_file("file", env_var="MYVAR")})
                    for the_os in ("Windows", "Linux"):
                        for prev in ("prev1", "prev2"):
                            with environment_update({"MYVAR": prev}):
                                client.run(f"create . --name={pkg} --version={version} "
                                           f"-s os={the_os}")
        return client

    @staticmethod
    def assert_uploaded(pattern, result, client, only_recipe=False, query=None):
        def ref_map(r):
            rev1 = "ad55a66b62acb63ffa99ea9b75c16b99"
            rev2 = "127fb537a658ad6a57153a038960dc53"
            pid1 = "ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715"
            pid2 = "9a4eb3c8701508aa9458b1a73d0633783ecc2270"
            if "Linux" in r:
                prev1 = "7ce684c6109943482b9174dd089e717b"
                prev2 = "772234192e8e4ba71b018d2e7c02423e"
            else:
                prev1 = "45f88f3c318bd43d1bc48a5d408a57ef"
                prev2 = "c5375d1f517ecb1ed6c9532b0f4d86aa"

            r = r.replace("prev1", prev1).replace("prev2", prev2).replace("Windows", pid1)
            r = r.replace("Linux", pid2).replace("rev1", rev1).replace("rev2", rev2)
            return r

        pattern = ref_map(pattern)
        only_recipe = "" if not only_recipe else "--only-recipe"
        query = "" if not query else f"-p={query}"
        client.run(f"upload {pattern} -r=default -c {only_recipe} {query}")
        out = str(client.out)

        uploaded_recipes = [f"{p}/{v}#{rr}" for p in result[0]
                            for v in result[1]
                            for rr in result[2]]
        uploaded_packages = [f"{r}:{pid}#{pr}" for r in uploaded_recipes
                             for pid in result[3]
                             for pr in result[4]]

        # Checks
        upload_recipe_count = out.count("Uploading recipe")
        skipped_recipe_count = len(re.findall("Recipe '.+' already in server, skipping", out))
        assert upload_recipe_count + skipped_recipe_count == len(uploaded_recipes)
        for recipe in uploaded_recipes:
            recipe = ref_map(recipe)
            upload = f"Uploading recipe '{recipe}" in out
            existing = f"Recipe '{recipe}' already in server" in out
            assert upload or existing
        upload_pkg_count = out.count("Uploading package")
        skipped_pkg_count = len(re.findall("Package '.+' already in server, skipping", out))
        assert upload_pkg_count + skipped_pkg_count == len(uploaded_packages)
        for pkg in uploaded_packages:
            pkg = ref_map(pkg)
            upload = f"Uploading package '{pkg}" in out
            existing = f"Package '{pkg}' already in server" in out
            assert upload or existing

    def test_all_latest(self, client):
        result = ("pkga", "pkgb"), ("1.0", "1.1"), ("rev2",), ("Windows", "Linux"), ("prev2",)
        self.assert_uploaded("*", result, client)

    def test_all(self, client):
        result = ("pkga", "pkgb"), ("1.0", "1.1"), ("rev1", "rev2",), ("Windows", "Linux"), \
                 ("prev1", "prev2")
        self.assert_uploaded("*#*:*#*", result, client)

    def test_pkg(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev2",), ("Windows", "Linux"), ("prev2",)
        self.assert_uploaded("pkga", result, client)

    def test_pkg_rrev(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev1",), ("Windows", "Linux"), ("prev2",)
        self.assert_uploaded("pkga#rev1", result, client)

    def test_pkg_rrevs(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev1", "rev2"), ("Windows", "Linux"), ("prev2",)
        self.assert_uploaded("pkga#*", result, client)

    def test_pkg_pid(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev2",), ("Windows",), ("prev2",)
        self.assert_uploaded("pkga:Windows", result, client)

    def test_pkg_rrev_pid(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev1",), ("Windows",), ("prev2",)
        self.assert_uploaded("pkga#rev1:Windows", result, client)

    def test_pkg_rrevs_pid(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev1", "rev2"), ("Windows",), ("prev2",)
        self.assert_uploaded("pkga#*:Windows", result, client)

    def test_pkg_rrev_pid_prev(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev1",), ("Windows",), ("prev1",)
        self.assert_uploaded("pkga#rev1:Windows#prev1", result, client)

    # Only recipes
    def test_all_latest_only_recipe(self, client):
        result = ("pkga", "pkgb"), ("1.0", "1.1"), ("rev2",), (), ()
        self.assert_uploaded("*", result, client, only_recipe=True)

    def test_pkg_only_recipe(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev2",), (), ()
        self.assert_uploaded("pkga", result, client, only_recipe=True)

    def test_pkg_rrev_only_recipe(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev1",), (), ()
        self.assert_uploaded("pkga#rev1", result, client, only_recipe=True)

    def test_pkg_rrevs_only_recipe(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev1", "rev2"), (), ()
        self.assert_uploaded("pkga#*", result, client, only_recipe=True)

    # Package query
    def test_pkg_query(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev2",), ("Windows",), ("prev2",)
        self.assert_uploaded("pkga", result, client, query="os=Windows")


@pytest.mark.xfail(reason="Pattern errors not defined yet")
class TestUploadPatternErrors:
    def test_upload_binary_not_existing(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=hello --version=0.1 --user=lasote --channel=testing")
        client.run("upload hello/0.1@lasote/testing:123 -r default", assert_error=True)
        assert "ERROR: No 'hello/0.1@lasote/testing' package_id matching '123'" in client.out
        # But this shouldn't be a problem
        client.run("upload hello/0.1@lasote/testing:* -r default -c")
        assert "WARN: No 'hello/0.1@lasote/testing' package_id matching '123'" in client.out

    def test_not_existing_error(self):
        """ Trying to upload with pattern not matched must raise an Error
        """
        client = TestClient(default_server_user=True)
        client.run("upload some_nonsense* -r default --only-recipe", assert_error=True)
        assert "No recipes found matching pattern 'some_nonsense*'" in client.out

    def test_non_existing_recipe_error(self):
        """ Trying to upload a non-existing recipe must raise an Error
        """
        client = TestClient(default_server_user=True)
        client.run("upload pkg/0.1@user/channel -r default --only-recipe", assert_error=True)
        self.assertIn("No recipes found matching pattern 'pkg/0.1@user/channel'", client.out)

    def test_non_existing_package_error(self):
        """ Trying to upload a non-existing package must raise an Error
        """
        client = TestClient(default_server_user=True)
        client.run("upload pkg/0.1@user/channel -r default --only-recipe", assert_error=True)
        self.assertIn("No recipes found matching pattern 'pkg/0.1@user/channel'", client.out)

    def test_upload_with_pref(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile})
        client.run("create . --user=user --channel=testing")
        client.run("upload hello0/1.2.1@user/testing#*:{} -c "
                   "-r default --only-recipe".format(NO_SETTINGS_PACKAGE_ID))
        print(client.out)
        self.assertIn("Uploading package 'hello0/1.2.1@user/testing#e9865516f03b8acbe2bd918d26b1460f"
                      ":da39a3ee5e6b4b0d3255bfef95601890afd80709#0ba8627bd47edc3a501e8f0eb9a79e5e'",
                      client.out)
