import re

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.env import environment_update


class TestDownloadPatterns:
    # FIXME The fixture is copied from TestUploadPatterns, reuse it
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
        client.run("upload *#*:*#* -r=default -c")
        return client

    @staticmethod
    def assert_downloaded(pattern, result, client, only_recipe=False, query=None):
        # FIXME: Also common to TestUploadPatterns
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
        client.run(f"download {pattern} -r=default {only_recipe} {query}")
        out = str(client.out)

        downloaded_recipes = [f"{p}/{v}#{rr}" for p in result[0]
                              for v in result[1]
                              for rr in result[2]]
        downloaded_packages = [f"{r}:{pid}#{pr}" for r in downloaded_recipes
                               for pid in result[3]
                               for pr in result[4]]

        # Checks
        skipped_recipe_count = len(re.findall("Skip recipe .+ download, already in cache", out))
        assert skipped_recipe_count == len(downloaded_recipes)
        for recipe in downloaded_recipes:
            recipe = ref_map(recipe)
            existing = f"Skip recipe {recipe} download, already in cache" in out
            assert existing
        skipped_pkg_count = len(re.findall("Skip package .+ download, already in cache", out))
        assert skipped_pkg_count == len(downloaded_packages)
        for pkg in downloaded_packages:
            pkg = ref_map(pkg)
            existing = f"Skip package {pkg} download, already in cache" in out
            assert existing

    def test_all_latest(self, client):
        result = ("pkga", "pkgb"), ("1.0", "1.1"), ("rev2",), ("Windows", "Linux"), ("prev2",)
        self.assert_downloaded("*", result, client)

    def test_all(self, client):
        result = ("pkga", "pkgb"), ("1.0", "1.1"), ("rev1", "rev2",), ("Windows", "Linux"), \
                 ("prev1", "prev2")
        self.assert_downloaded("*#*:*#*", result, client)

    def test_pkg(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev2",), ("Windows", "Linux"), ("prev2",)
        self.assert_downloaded("pkga", result, client)

    def test_pkg_rrev(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev1",), ("Windows", "Linux"), ("prev2",)
        self.assert_downloaded("pkga#rev1", result, client)

    def test_pkg_rrevs(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev1", "rev2"), ("Windows", "Linux"), ("prev2",)
        self.assert_downloaded("pkga#*", result, client)

    def test_pkg_pid(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev2",), ("Windows",), ("prev2",)
        self.assert_downloaded("pkga:Windows", result, client)

    def test_pkg_rrev_pid(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev1",), ("Windows",), ("prev2",)
        self.assert_downloaded("pkga#rev1:Windows", result, client)

    def test_pkg_rrevs_pid(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev1", "rev2"), ("Windows",), ("prev2",)
        self.assert_downloaded("pkga#*:Windows", result, client)

    def test_pkg_rrev_pid_prev(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev1",), ("Windows",), ("prev1",)
        self.assert_downloaded("pkga#rev1:Windows#prev1", result, client)

    # Only recipes
    def test_all_latest_only_recipe(self, client):
        result = ("pkga", "pkgb"), ("1.0", "1.1"), ("rev2",), (), ()
        self.assert_downloaded("*", result, client, only_recipe=True)

    def test_pkg_only_recipe(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev2",), (), ()
        self.assert_downloaded("pkga", result, client, only_recipe=True)

    def test_pkg_rrev_only_recipe(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev1",), (), ()
        self.assert_downloaded("pkga#rev1", result, client, only_recipe=True)

    def test_pkg_rrevs_only_recipe(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev1", "rev2"), (), ()
        self.assert_downloaded("pkga#*", result, client, only_recipe=True)

    # Package query
    def test_pkg_query(self, client):
        result = ("pkga",), ("1.0", "1.1"), ("rev2",), ("Windows",), ("prev2",)
        self.assert_downloaded("pkga", result, client, query="os=Windows")


@pytest.mark.xfail(reason="Pattern errors not defined yet")
class TestDownloadPatterErrors:

    def test_download_revs_enabled_with_fake_rrev(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=pkg --version=1.0 --user=user --channel=channel")
        client.run("upload * --confirm -r default")
        client.run("remove * -f")
        client.run("download pkg/1.0@user/channel#fakerevision -r default", assert_error=True)
        self.assertIn("ERROR: There are no recipes matching 'pkg/1.0@user/channel#fakerevision'", client.out)

    def test_download_all_but_no_packages():
        # Remove all from remote
        new_client = TestClient(default_server_user=True)

        # Try to install all
        new_client.run("download hello0/0.1@lasote/stable:* -r default", assert_error=True)
        assert "Recipe not found: 'hello0/0.1@lasote/stable'" in new_client.out

        # Upload the recipe (we don't have packages)
        new_client.save({"conanfile.py": GenConanfile()})
        new_client.run("export . --name=hello0 --version=0.1 --user=lasote --channel=stable")
        new_client.run("upload hello0/0.1@lasote/stable -r default")

        # And try to download all
        new_client.run("download hello0/0.1@lasote/stable:* -r default", assert_error=True)
        assert "There are no packages matching 'hello0/0.1@lasote/stable:*'" in new_client.out

    def test_download_wrong_id(self):
        client = TurboTestClient(default_server_user=True)
        ref = RecipeReference.loads("pkg/0.1@lasote/stable")
        client.export(ref)
        rrev = client.exported_recipe_revision()
        client.upload_all(ref)
        client.remove_all()

        client.run("download pkg/0.1@lasote/stable#{}:wrong -r default".format(rrev),
                   assert_error=True)
        self.assertIn("ERROR: There are no packages matching "
                      "'pkg/0.1@lasote/stable#{}:wrong".format(rrev), client.out)

    def test_download_not_found_reference(self):
        client = TurboTestClient(default_server_user=True)
        client.run("download pkg/0.1@lasote/stable -r default", assert_error=True)
        self.assertIn("ERROR: Recipe not found: 'pkg/0.1@lasote/stable'", client.out)

    def test_download_reference_without_packages(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile().with_name("pkg").with_version("0.1")})
        client.run("export . --user=user --channel=stable")
        client.run("upload pkg/0.1@user/stable -r default")
        client.run("remove pkg/0.1@user/stable -f")

        client.run("download pkg/0.1@user/stable#*:* -r default", assert_error=True)
        # Check 'No remote binary packages found' warning
        self.assertIn("There are no packages matching", client.out)
        # The recipe is not downloaded either
        client.run("list recipes pkg*")
        assert "There are no matching recipe references" in client.out
