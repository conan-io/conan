import re

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer


class TestListRecipeRevisionsBase:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.client = TestClient()

    def _add_remote(self, remote_name):
        self.client.servers[remote_name] = TestServer(users={"username": "passwd"}, write_permissions=[("*/*@*/*", "*")])
        self.client.update_servers()
        self.client.run("user username -p passwd -r {}".format(remote_name))

    def _create_recipe(self, reference):
        self.client.save({'conanfile.py': GenConanfile()})
        self.client.run("create . {}".format(reference))

    def _upload_recipe(self, remote, reference):
        self.client.save({'conanfile.py': GenConanfile()})
        self.client.run("export . {}".format(reference))
        self.client.run("upload --force -r {} {}".format(remote, reference))


class TestParams(TestListRecipeRevisionsBase):
    def test_fail_if_reference_is_not_correct(self):
        self.client.run("list recipe-revisions whatever", assert_error=True)
        assert "ERROR: Specify the 'name' and the 'version'" in self.client.out

        self.client.run("list recipe-revisions whatever/", assert_error=True)
        assert "ERROR: Specify the 'name' and the 'version'" in self.client.out

        self.client.run("list recipe-revisions whatever/1", assert_error=True)
        assert "ERROR: Value provided for package version, '1' (type Version), is too short" in self.client.out

    def test_query_param_is_required(self):
        self._add_remote("remote1")

        self.client.run("list recipe-revisions", assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

        self.client.run("list recipe-revisions -c", assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

        self.client.run("list recipe-revisions --all-remotes", assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

        self.client.run("list recipe-revisions --remote remote1 --cache", assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

    def test_remote_and_all_remotes_are_mutually_exclusive(self):
        self._add_remote("remote1")

        self.client.run("list recipe-revisions --all-remotes --remote remote1 package/1.0", assert_error=True)
        assert "error: argument -r/--remote: not allowed with argument -a/--all-remotes" in self.client.out


class TestListRecipesFromRemotes(TestListRecipeRevisionsBase):
    def test_by_default_search_only_in_cache(self):
        self._add_remote("remote1")
        self._add_remote("remote2")

        expected_output = ("Local Cache:\n"
                           "  There are no matching recipes\n")

        self.client.run("list recipe-revisions whatever/1.0")
        assert expected_output == self.client.out

    def test_search_no_matching_recipes(self):
        self._add_remote("remote1")
        self._add_remote("remote2")

        expected_output = ("Local Cache:\n"
                           "  There are no matching recipes\n"
                           "remote1:\n"
                           "  There are no matching recipes\n"
                           "remote2:\n"
                           "  There are no matching recipes\n")

        self.client.run("list recipe-revisions -c -a whatever/1.0")
        assert expected_output == self.client.out

    def test_fail_if_no_configured_remotes(self):
        self.client.run("list recipe-revisions -a whatever/1.0", assert_error=True)
        assert "ERROR: The remotes registry is empty" in self.client.out

    def test_search_disabled_remote(self):
        self._add_remote("remote1")
        self.client.run("remote disable remote1")
        self.client.run("list recipe-revisions -r remote1 whatever/1.0", assert_error=True)
        assert "ERROR: Remote 'remote1' is disabled" in self.client.out


class TestRemotes(TestListRecipeRevisionsBase):
    def test_search_with_full_reference(self):
        remote_name = "remote1"
        recipe_name = "test_recipe/1.0.0@user/channel"
        self._add_remote(remote_name)
        self._upload_recipe(remote_name, recipe_name)

        self.client.run("list recipe-revisions -r remote1 test_recipe/1.0.0@user/channel")

        expected_output = (
            r"remote1:\n"
            r"  {}#.*\n".format(recipe_name)
        )

        assert bool(re.match(expected_output, str(self.client.out), re.MULTILINE))

    def test_search_without_user_and_channel(self):
        remote_name = "remote1"
        recipe_name = "test_recipe/1.0.0@user/channel"
        self._add_remote(remote_name)
        self._upload_recipe(remote_name, recipe_name)

        self.client.run("list recipe-revisions -r remote1 test_recipe/1.0.0")

        expected_output = (
            "remote1:\n"
            "  There are no matching recipes\n"
        )

        assert expected_output in self.client.out

    def test_search_in_all_remotes_and_cache(self):
        expected_output = (
            r"Local Cache:\n"
            r"  test_recipe/1.0.0@user/channel#.*\n"
            r"remote1:\n"
            r"  test_recipe/1.0.0@user/channel#.*\n"
            r"remote2:\n"
            r"  There are no matching recipes\n"
        )

        remote1 = "remote1"
        remote2 = "remote2"

        self._add_remote(remote1)
        self._upload_recipe(remote1, "test_recipe/1.0.0@user/channel")
        self._upload_recipe(remote1, "test_recipe/1.1.0@user/channel")

        self._add_remote(remote2)
        self._upload_recipe(remote2, "test_recipe/2.0.0@user/channel")
        self._upload_recipe(remote2, "test_recipe/2.1.0@user/channel")

        self.client.run("list recipe-revisions -a -c test_recipe/1.0.0@user/channel")
        output = str(self.client.out)

        assert bool(re.match(expected_output, output, re.MULTILINE))

    def test_search_in_missing_remote(self):
        remote1 = "remote1"

        remote1_recipe1 = "test_recipe/1.0.0@user/channel"
        remote1_recipe2 = "test_recipe/1.1.0@user/channel"

        expected_output = "No remote 'wrong_remote' defined in remotes"

        self._add_remote(remote1)
        self._upload_recipe(remote1, remote1_recipe1)
        self._upload_recipe(remote1, remote1_recipe2)

        self.client.run("list recipe-revisions -r wrong_remote test_recipe/1.0.0@user/channel", assert_error=True)
        assert expected_output in self.client.out

    def test_wildcard_not_accepted(self):
        remote1 = "remote1"
        remote1_recipe1 = "test_recipe/1.0.0@user/channel"

        expected_output = "is an invalid name. Valid names MUST begin with a letter, number or underscore"

        self._add_remote(remote1)
        self._upload_recipe(remote1, remote1_recipe1)
        self.client.run("list recipe-revisions -a -c test_*", assert_error=True)

        assert expected_output in self.client.out
