import re
import textwrap
from unittest.mock import Mock, patch

import pytest

from conans.client.remote_manager import RemoteManager
from conans.errors import ConanConnectionError, ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer, NO_SETTINGS_PACKAGE_ID


class TestListPackageRevisionsBase:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.users = {}
        self.client = TestClient()

    def _add_remote(self, remote_name):
        self.client.servers[remote_name] = TestServer(users={"username": "passwd"},
                                                      write_permissions=[("*/*@*/*", "*")])
        self.client.update_servers()
        self.client.run("remote login {} username -p passwd".format(remote_name))

    def _upload_recipe(self, remote, ref):
        self.client.save({'conanfile.py': GenConanfile()})
        ref = RecipeReference.loads(ref)
        self.client.run(f"create . --name={ref.name} --version={ref.version} --user={ref.user} --channel={ref.channel}")
        self.client.run("upload --force -r {} {}".format(remote, ref))

    @staticmethod
    def _get_fake_package_refence(recipe_name):
        return f"{recipe_name}#fca0383e6a43348f7989f11ab8f0a92d:" \
               f"3fb49604f9c2f729b85ba3115852006824e72cab"

    def _get_lastest_package_ref(self, recipe_name):
        rref = self.client.cache.get_latest_recipe_reference(RecipeReference.loads(recipe_name))
        pref = PkgReference(rref, NO_SETTINGS_PACKAGE_ID)
        return pref


class TestParams(TestListPackageRevisionsBase):

    @pytest.mark.parametrize("ref", [
        "whatever",
        "whatever/",
        "whatever/1"
    ])
    def test_fail_if_reference_is_not_correct(self, ref):
        self.client.run(f"list package-revisions {ref}", assert_error=True)
        assert f"ERROR: {ref} is not a valid package reference, provide a " \
               f"reference in the form name/version[@user/channel]#RECIPE_REVISION:PACKAGE_ID" in self.client.out

    def test_fails_if_reference_has_already_the_revision(self):
        pref = self._get_fake_package_refence("whatever/1.0.0")
        self.client.run(f"list package-revisions {pref}#fca0383e6a43348f7989f11ab8f0a92d", assert_error=True)
        assert "ERROR: Cannot list the revisions of a specific package revision" in self.client.out

    def test_query_param_is_required(self):
        self._add_remote("remote1")

        self.client.run("list package-revisions", assert_error=True)
        assert "error: the following arguments are required: package_reference" in self.client.out

        self.client.run("list package-revisions -c", assert_error=True)
        assert "error: the following arguments are required: package_reference" in self.client.out

        self.client.run('list package-revisions -r="*"', assert_error=True)
        assert "error: the following arguments are required: package_reference" in self.client.out

        self.client.run("list package-revisions --remote remote1 --cache", assert_error=True)
        assert "error: the following arguments are required: package_reference" in self.client.out

    def test_wildcard_not_accepted(self):
        self.client.run('list package-revisions -r="*" -c test_*', assert_error=True)
        expected_output = "ERROR: test_* is not a valid package reference, provide a " \
                          "reference in the form name/version[@user/channel]#RECIPE_REVISION:PACKAGE_ID"
        assert expected_output in self.client.out


class TestListPackagesFromRemotes(TestListPackageRevisionsBase):
    def test_by_default_search_only_in_cache(self):
        self._add_remote("remote1")
        self._add_remote("remote2")

        expected_output = textwrap.dedent("""\
        Local Cache:
          There are no matching package references
        """)

        self.client.run(f"list package-revisions {self._get_fake_package_refence('whatever/0.1')}")
        assert expected_output == self.client.out

    def test_search_no_matching_recipes(self):
        self._add_remote("remote1")
        self._add_remote("remote2")

        expected_output = textwrap.dedent("""\
        Local Cache:
          There are no matching package references
        remote1:
          ERROR: Recipe or package not found: 'whatever/0.1:3fb49604f9c2f729b85ba3115852006824e72cab'. [Remote: remote1]
        remote2:
          ERROR: Recipe or package not found: 'whatever/0.1:3fb49604f9c2f729b85ba3115852006824e72cab'. [Remote: remote2]
        """)

        pref = self._get_fake_package_refence('whatever/0.1')
        self.client.run(f'list package-revisions -c -r="*" {pref}')
        assert expected_output == self.client.out

    def test_fail_if_no_configured_remotes(self):
        pref = self._get_fake_package_refence('whatever/0.1')
        self.client.run(f'list package-revisions -r="*" {pref}', assert_error=True)
        assert "ERROR: Remotes for pattern '*' can't be found or are disabled" in self.client.out

    def test_search_disabled_remote(self):
        self._add_remote("remote1")
        self._add_remote("remote2")
        self.client.run("remote disable remote1")
        # He have to put both remotes instead of using "-a" because of the
        # disbaled remote won't appear
        pref = self._get_fake_package_refence('whatever/0.1')
        self.client.run(f"list package-revisions {pref} -r remote1 -r remote2", assert_error=True)
        assert "Remotes for pattern 'remote1' can't be found or are disabled" in self.client.out

    @pytest.mark.parametrize("exc,output", [
        (ConanConnectionError("Review your network!"),
         "ERROR: Review your network!"),
        (ConanException("Boom!"), "ERROR: Boom!")
    ])
    def test_search_remote_errors_but_no_raising_exceptions(self, exc, output):
        self._add_remote("remote1")
        self._add_remote("remote2")
        pref = self._get_fake_package_refence('whatever/0.1')
        with patch.object(RemoteManager, "get_package_revisions_references",
                          new=Mock(side_effect=exc)):
            self.client.run(f'list package-revisions {pref} -r="*" -c')
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          There are no matching package references
        remote1:
          {output}
        remote2:
          {output}
        """)
        assert expected_output == self.client.out


class TestRemotes(TestListPackageRevisionsBase):
    def test_search_with_full_reference(self):
        remote_name = "remote1"
        recipe_name = "test_recipe/1.0.0@user/channel"
        self._add_remote(remote_name)
        self._upload_recipe(remote_name, recipe_name)
        pref = self._get_lastest_package_ref("test_recipe/1.0.0@user/channel")
        self.client.run(f"list package-revisions -r remote1 {repr(pref)}")

        expected_output = textwrap.dedent(f"""\
        remote1:
          {pref.repr_notime()}""")

        assert bool(re.match(expected_output, str(self.client.out), re.MULTILINE))

    def test_search_in_all_remotes_and_cache(self):
        remote1 = "remote1"
        remote2 = "remote2"

        self._add_remote(remote1)
        self._upload_recipe(remote1, "test_recipe/1.0.0@user/channel")
        self._upload_recipe(remote1, "test_recipe/1.1.0@user/channel")

        self._add_remote(remote2)
        self._upload_recipe(remote2, "test_recipe/2.0.0@user/channel")
        self._upload_recipe(remote2, "test_recipe/2.1.0@user/channel")

        pref = self._get_lastest_package_ref("test_recipe/1.0.0@user/channel")
        self.client.run(f'list package-revisions -r="*" -c {repr(pref)}')
        output = str(self.client.out)
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          {pref.repr_notime()}.*
        remote1:
          {pref.repr_notime()}.*
        remote2:
          ERROR: Recipe not found:*""")
        assert bool(re.match(expected_output, output, re.MULTILINE))

    def test_search_in_missing_remote(self):
        remote1 = "remote1"

        remote1_recipe1 = "test_recipe/1.0.0@user/channel"
        remote1_recipe2 = "test_recipe/1.1.0@user/channel"

        expected_output = "ERROR: Remote 'wrong_remote' not found in remotes"

        self._add_remote(remote1)
        self._upload_recipe(remote1, remote1_recipe1)
        self._upload_recipe(remote1, remote1_recipe2)

        pref = self._get_fake_package_refence(remote1_recipe1)
        self.client.run(f"list package-revisions -r wrong_remote {pref}", assert_error=True)
        assert expected_output in self.client.out
