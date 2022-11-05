import re
import textwrap
from unittest.mock import patch, Mock

import pytest

from conans.client.remote_manager import RemoteManager
from conans.errors import ConanException, ConanConnectionError
from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer


class TestListRecipeRevisionsBase:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.client = TestClient()

    def _add_remote(self, remote_name):
        self.client.servers[remote_name] = TestServer(users={"username": "passwd"}, write_permissions=[("*/*@*/*", "*")])
        self.client.update_servers()
        self.client.run("remote login {} username -p passwd".format(remote_name))

    def _create_recipe(self, reference):
        self.client.save({'conanfile.py': GenConanfile()})
        self.client.run("create . {}".format(reference))

    def _upload_recipe(self, remote, reference):
        reference = RecipeReference.loads(str(reference))
        self.client.save({'conanfile.py': GenConanfile()})
        self.client.run(f"export . --name={reference.name} --version={reference.version} --user={reference.user} --channel={reference.channel}")
        self.client.run("upload --force -r {} {}".format(remote, reference))


class TestParams(TestListRecipeRevisionsBase):
    @pytest.mark.parametrize("ref", [
        "whatever",
        "whatever/"
    ])
    def test_fail_if_reference_is_not_correct(self, ref):
        self.client.run(f"list recipe-revisions {ref}", assert_error=True)
        assert f"ERROR: {ref} is not a valid recipe reference, provide a " \
               f"reference in the form name/version[@user/channel]" in self.client.out

    def test_query_param_is_required(self):
        self._add_remote("remote1")

        self.client.run("list recipe-revisions", assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

        self.client.run("list recipe-revisions -c", assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

        self.client.run('list recipe-revisions -r="*"', assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

        self.client.run("list recipe-revisions --remote remote1 --cache", assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

    def test_wildcard_not_accepted(self):
        self.client.run('list recipe-revisions -r="*" -c test_*', assert_error=True)
        expected_output = "ERROR: test_* is not a valid recipe reference, provide a " \
                          "reference in the form name/version[@user/channel]"
        assert expected_output in self.client.out


class TestListRecipesFromRemotes(TestListRecipeRevisionsBase):
    def test_by_default_search_only_in_cache(self):
        self._add_remote("remote1")
        self._add_remote("remote2")

        expected_output = ("Local Cache:\n"
                           "  There are no matching recipe references\n")

        self.client.run("list recipe-revisions whatever/1.0")
        assert expected_output == self.client.out

    def test_search_no_matching_recipes(self):
        self._add_remote("remote1")
        self._add_remote("remote2")

        expected_output = ("Local Cache:\n"
                           "  There are no matching recipe references\n"
                           "remote1:\n"
                           "  ERROR: Recipe not found: 'whatever/1.0'. [Remote: remote1]\n"
                           "remote2:\n"
                           "  ERROR: Recipe not found: 'whatever/1.0'. [Remote: remote2]\n")

        self.client.run('list recipe-revisions -r="*" -c whatever/1.0')
        assert expected_output == self.client.out

    def test_fail_if_no_configured_remotes(self):
        self.client.run('list recipe-revisions -r="*" whatever/1.0', assert_error=True)
        assert "ERROR: Remotes for pattern '*' can't be found or are disabled" in self.client.out

    def test_search_disabled_remote(self):
        self._add_remote("remote1")
        self._add_remote("remote2")
        self.client.run("remote disable remote1")
        # He have to put both remotes instead of using "-a" because of the
        # disbaled remote won't appear
        self.client.run("list recipe-revisions whatever/1.0 -r remote1 -r remote2",
                        assert_error=True)
        assert "Remotes for pattern 'remote1' can't be found or are disabled" in self.client.out

    @pytest.mark.parametrize("exc,output", [
        (ConanConnectionError("Review your network!"),
         "ERROR: Review your network!"),
        (ConanException("Boom!"), "ERROR: Boom!")
    ])
    def test_search_remote_errors_but_no_raising_exceptions(self, exc, output):
        self._add_remote("remote1")
        self._add_remote("remote2")
        with patch.object(RemoteManager, "get_recipe_revisions_references",
                          new=Mock(side_effect=exc)):
            self.client.run('list recipe-revisions whatever/1.0 -r="*" -c')
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          There are no matching recipe references
        remote1:
          {output}
        remote2:
          {output}
        """)
        assert expected_output == self.client.out


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
            "  ERROR: Recipe not found: 'test_recipe/1.0.0'. [Remote: remote1]\n"
        )

        assert expected_output in self.client.out

    def test_search_in_all_remotes_and_cache(self):
        expected_output = (
            r"Local Cache:\n"
            r"  test_recipe/1.0.0@user/channel#.*\n"
            r"remote1:\n"
            r"  test_recipe/1.0.0@user/channel#.*\n"
            r"remote2:\n"
            r"  ERROR: Recipe not found: 'test_recipe/1.0.0@user/channel'.*\n"
        )

        remote1 = "remote1"
        remote2 = "remote2"

        self._add_remote(remote1)
        self._upload_recipe(remote1, "test_recipe/1.0.0@user/channel")
        self._upload_recipe(remote1, "test_recipe/1.1.0@user/channel")

        self._add_remote(remote2)
        self._upload_recipe(remote2, "test_recipe/2.0.0@user/channel")
        self._upload_recipe(remote2, "test_recipe/2.1.0@user/channel")

        self.client.run('list recipe-revisions -r="*" -c test_recipe/1.0.0@user/channel')
        output = str(self.client.out)
        assert bool(re.match(expected_output, output, re.MULTILINE))

    def test_search_in_missing_remote(self):
        remote1 = "remote1"

        remote1_recipe1 = "test_recipe/1.0.0@user/channel"
        remote1_recipe2 = "test_recipe/1.1.0@user/channel"

        expected_output = "ERROR: Remotes for pattern 'wrong_remote' can't be found or are disabled"

        self._add_remote(remote1)
        self._upload_recipe(remote1, remote1_recipe1)
        self._upload_recipe(remote1, remote1_recipe2)

        self.client.run("list recipe-revisions -r wrong_remote test_recipe/1.0.0@user/channel", assert_error=True)
        assert expected_output in self.client.out
