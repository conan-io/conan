import re
import textwrap
from unittest.mock import patch

import pytest

from conans.errors import ConanConnectionError, ConanException
from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer


class TestListRecipesBase:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.users = {}
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


class TestParams(TestListRecipesBase):
    def test_fail_if_remote_list_is_empty(self):
        self.client.run("list recipes -r whatever *", assert_error=True)
        assert "ERROR: Remote 'whatever' can't be found or is disabled" in self.client.out

    def test_query_param_is_required(self):
        self._add_remote("remote1")

        self.client.run("list recipes", assert_error=True)
        assert "error: the following arguments are required: query" in self.client.out

        self.client.run("list recipes -c", assert_error=True)
        assert "error: the following arguments are required: query" in self.client.out

        self.client.run('list recipes -r="*"', assert_error=True)
        assert "error: the following arguments are required: query" in self.client.out

        self.client.run("list recipes --remote remote1 --cache", assert_error=True)
        assert "error: the following arguments are required: query" in self.client.out


class TestListRecipesFromRemotes(TestListRecipesBase):
    def test_by_default_search_only_in_cache(self):
        self._add_remote("remote1")
        self._add_remote("remote2")

        expected_output = ("Local Cache:\n"
                           "  There are no matching recipe references\n")

        self.client.run("list recipes whatever")
        assert expected_output == self.client.out

    def test_search_no_matching_recipes(self):
        self._add_remote("remote1")
        self._add_remote("remote2")

        expected_output = ("Local Cache:\n"
                           "  There are no matching recipe references\n"
                           "remote1:\n"
                           "  There are no matching recipe references\n"
                           "remote2:\n"
                           "  There are no matching recipe references\n")

        self.client.run('list recipes -c -r="*" whatever')
        assert expected_output == self.client.out

    def test_fail_if_no_configured_remotes(self):
        self.client.run('list recipes -r="*" whatever', assert_error=True)
        assert "Remotes for pattern '*' can't be found or are disabled" in self.client.out

    def test_search_disabled_remote(self):
        self._add_remote("remote1")
        self._add_remote("remote2")
        self.client.run("remote disable remote1")
        # He have to put both remotes instead of using "-a" because of the
        # disbaled remote won't appear
        self.client.run("list recipes whatever -r remote1 -r remote2", assert_error=True)
        assert "ERROR: Remote 'remote1' can't be found or is disabled" in self.client.out

    @pytest.mark.parametrize("exc,output", [
        (ConanConnectionError("Review your network!"),
         "ERROR: Review your network!"),
        (ConanException("Boom!"), "ERROR: Boom!")
    ])
    def test_search_remote_errors_but_no_raising_exceptions(self, exc, output):
        self._add_remote("remote1")
        self._add_remote("remote2")

        def boom_if_remote(self, query: str, remote=None):
            if remote:
                raise exc
            return []
        with patch("conan.api.subapi.search.SearchAPI.recipes", new=boom_if_remote):
            self.client.run('list recipes whatever -r="*" -c')
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          There are no matching recipe references
        remote1:
          {output}
        remote2:
          {output}
        """)
        assert expected_output == self.client.out


class TestRemotes(TestListRecipesBase):
    def test_search_by_name(self):
        remote_name = "remote1"
        recipe_name = "test_recipe/1.0.0@user/channel"
        self._add_remote(remote_name)
        self._upload_recipe(remote_name, recipe_name)

        self.client.run("remote list")
        assert "remote1: http://fake" in self.client.out

        self.client.run("list recipes -r {} {}".format(remote_name, "test_recipe"))

        expected_output = (
            "remote1:\n"
            "  test_recipe\n"
            "    {}\n".format(recipe_name)
        )

        assert expected_output == self.client.out

    def test_search_in_all_remotes_and_cache(self):
        expected_output = (
            r"Local Cache:\n"
            r"  test_recipe\n"
            r"    test_recipe/2.1.0@user/channel\n"
            r"    test_recipe/2.0.0@user/channel\n"
            r"    test_recipe/1.1.0@user/channel\n"
            r"    test_recipe/1.0.0@user/channel\n"
            r"remote1:\n"
            r"  test_recipe\n"
            r"    test_recipe/1.0.0@user/channel\n"
            r"    test_recipe/1.1.0@user/channel\n"
            r"remote2:\n"
            r"  test_recipe\n"
            r"    test_recipe/2.0.0@user/channel\n"
            r"    test_recipe/2.1.0@user/channel\n"
        )

        remote1 = "remote1"
        remote2 = "remote2"

        self._add_remote(remote1)
        self._upload_recipe(remote1, "test_recipe/1.0.0@user/channel")
        self._upload_recipe(remote1, "test_recipe/1.1.0@user/channel")

        self._add_remote(remote2)
        self._upload_recipe(remote2, "test_recipe/2.0.0@user/channel")
        self._upload_recipe(remote2, "test_recipe/2.1.0@user/channel")

        self.client.run('list recipes -r="*" -c test_recipe')
        output = str(self.client.out)

        assert bool(re.match(expected_output, output, re.MULTILINE))

    def test_search_in_all_remotes(self):
        expected_output = (
            r"remote1:\n"
            r"  test_recipe\n"
            r"    test_recipe/1.0.0@user/channel\n"
            r"    test_recipe/1.1.0@user/channel\n"
            r"remote2:\n"
            r"  test_recipe\n"
            r"    test_recipe/2.0.0@user/channel\n"
            r"    test_recipe/2.1.0@user/channel\n"
        )

        remote1 = "remote1"
        remote2 = "remote2"

        self._add_remote(remote1)
        self._upload_recipe(remote1, "test_recipe/1.0.0@user/channel")
        self._upload_recipe(remote1, "test_recipe/1.1.0@user/channel")

        self._add_remote(remote2)
        self._upload_recipe(remote2, "test_recipe/2.0.0@user/channel")
        self._upload_recipe(remote2, "test_recipe/2.1.0@user/channel")

        self.client.run('list recipes -r="*" test_recipe')
        output = str(self.client.out)

        assert bool(re.match(expected_output, output, re.MULTILINE))

    def test_search_in_one_remote(self):
        remote1 = "remote1"
        remote2 = "remote2"

        remote1_recipe1 = "test_recipe/1.0.0@user/channel"
        remote1_recipe2 = "test_recipe/1.1.0@user/channel"
        remote2_recipe1 = "test_recipe/2.0.0@user/channel"
        remote2_recipe2 = "test_recipe/2.1.0@user/channel"

        expected_output = (
            "remote1:\n"
            "  test_recipe\n"
            "    test_recipe/1.0.0@user/channel\n"
            "    test_recipe/1.1.0@user/channel\n"
        )

        self._add_remote(remote1)
        self._upload_recipe(remote1, remote1_recipe1)
        self._upload_recipe(remote1, remote1_recipe2)

        self._add_remote(remote2)
        self._upload_recipe(remote2, remote2_recipe1)
        self._upload_recipe(remote2, remote2_recipe2)

        self.client.run("list recipes -r remote1 test_recipe")
        assert expected_output in self.client.out

    def test_search_package_found_in_one_remote(self):

        remote1 = "remote1"
        remote2 = "remote2"

        remote1_recipe1 = "test_recipe/1.0.0@user/channel"
        remote1_recipe2 = "test_recipe/1.1.0@user/channel"
        remote2_recipe1 = "another_recipe/2.0.0@user/channel"
        remote2_recipe2 = "another_recipe/2.1.0@user/channel"

        expected_output = (
            r"Local Cache:\n"
            r"  test_recipe\n"
            r"    test_recipe/1.1.0@user/channel\n"
            r"    test_recipe/1.0.0@user/channel\n"
            r"remote1:\n"
            r"  test_recipe\n"
            r"    test_recipe/1.0.0@user/channel\n"
            r"    test_recipe/1.1.0@user/channel\n"
            r"remote2:\n"
            r"  There are no matching recipe references\n"
        )

        self._add_remote(remote1)
        self._upload_recipe(remote1, remote1_recipe1)
        self._upload_recipe(remote1, remote1_recipe2)

        self._add_remote(remote2)
        self._upload_recipe(remote2, remote2_recipe1)
        self._upload_recipe(remote2, remote2_recipe2)

        self.client.run('list recipes -r="*" -c test_recipe')

        output = str(self.client.out)
        assert bool(re.match(expected_output, output, re.MULTILINE))

    def test_search_in_missing_remote(self):
        remote1 = "remote1"

        remote1_recipe1 = "test_recipe/1.0.0@user/channel"
        remote1_recipe2 = "test_recipe/1.1.0@user/channel"

        expected_output = "ERROR: Remote 'wrong_remote' can't be found or is disabled"

        self._add_remote(remote1)
        self._upload_recipe(remote1, remote1_recipe1)
        self._upload_recipe(remote1, remote1_recipe2)

        self.client.run("list recipes -r wrong_remote test_recipe", assert_error=True)
        assert expected_output in self.client.out

    def test_search_wildcard(self):
        remote1 = "remote1"

        remote1_recipe1 = "test_recipe/1.0.0@user/channel"
        remote1_recipe2 = "test_recipe/1.1.0@user/channel"
        remote1_recipe3 = "test_another/2.1.0@user/channel"
        remote1_recipe4 = "test_another/4.1.0@user/channel"

        expected_output = (
            r"Local Cache:\n"
            r"  test_another\n"
            r"    test_another/4.1.0@user/channel\n"
            r"    test_another/2.1.0@user/channel\n"
            r"  test_recipe\n"
            r"    test_recipe/1.1.0@user/channel\n"
            r"    test_recipe/1.0.0@user/channel\n"
            r"remote1:\n"
            r"  test_another\n"
            r"    test_another/2.1.0@user/channel\n"
            r"    test_another/4.1.0@user/channel\n"
            r"  test_recipe\n"
            r"    test_recipe/1.0.0@user/channel\n"
            r"    test_recipe/1.1.0@user/channel\n"
        )

        self._add_remote(remote1)
        self._upload_recipe(remote1, remote1_recipe1)
        self._upload_recipe(remote1, remote1_recipe2)
        self._upload_recipe(remote1, remote1_recipe3)
        self._upload_recipe(remote1, remote1_recipe4)

        self.client.run('list recipes -r "*" -c test_*')
        output = str(self.client.out)
        assert bool(re.match(expected_output, output, re.MULTILINE))
