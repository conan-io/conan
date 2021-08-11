import re
import textwrap
from unittest.mock import Mock, patch

import pytest

from conans.client.remote_manager import RemoteManager
from conans.errors import ConanConnectionError, ConanException
from conans.model.ref import ConanFileReference, PackageReference
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
        self.client.run("user username -p passwd -r {}".format(remote_name))

    def _upload_recipe(self, remote, reference):
        self.client.save({'conanfile.py': GenConanfile()})
        self.client.run("create . {}".format(reference))
        self.client.run("upload --force --all -r {} {}".format(remote, reference))

    @staticmethod
    def _get_fake_package_refence(recipe_name):
        return f"{recipe_name}#fca0383e6a43348f7989f11ab8f0a92d:" \
               f"3fb49604f9c2f729b85ba3115852006824e72cab"

    def _get_lastest_package_ref(self, recipe_name):
        rref = self.client.cache.get_latest_rrev(ConanFileReference.loads(recipe_name))
        pref = PackageReference(rref, NO_SETTINGS_PACKAGE_ID)
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

        self.client.run("list package-revisions --all-remotes", assert_error=True)
        assert "error: the following arguments are required: package_reference" in self.client.out

        self.client.run("list package-revisions --remote remote1 --cache", assert_error=True)
        assert "error: the following arguments are required: package_reference" in self.client.out

    def test_remote_and_all_remotes_are_mutually_exclusive(self):
        self._add_remote("remote1")

        self.client.run("list package-revisions --all-remotes --remote remote1 package/1.0", assert_error=True)
        assert "error: argument -r/--remote: not allowed with argument -a/--all-remotes" in self.client.out

    def test_wildcard_not_accepted(self):
        self.client.run("list package-revisions -a -c test_*", assert_error=True)
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
          There are no matching package references
        remote2:
          There are no matching package references
        """)

        pref = self._get_fake_package_refence('whatever/0.1')
        self.client.run(f"list package-revisions -c -a {pref}")
        assert expected_output == self.client.out

    def test_fail_if_no_configured_remotes(self):
        pref = self._get_fake_package_refence('whatever/0.1')
        self.client.run(f"list package-revisions -a {pref}", assert_error=True)
        assert "ERROR: The remotes registry is empty" in self.client.out

    def test_search_disabled_remote(self):
        self._add_remote("remote1")
        self._add_remote("remote2")
        self.client.run("remote disable remote1")
        # He have to put both remotes instead of using "-a" because of the
        # disbaled remote won't appear
        pref = self._get_fake_package_refence('whatever/0.1')
        self.client.run(f"list package-revisions {pref} -r remote1 -r remote2")
        expected_output = textwrap.dedent("""\
        remote1:
          ERROR: Remote 'remote1' is disabled
        remote2:
          There are no matching package references
        """)
        assert expected_output == self.client.out

    @pytest.mark.parametrize("exc,output", [
        (ConanConnectionError("Review your network!"),
         "There was a connection problem: Review your network!"),
        (ConanException("Boom!"), "Boom!")
    ])
    def test_search_remote_errors_but_no_raising_exceptions(self, exc, output):
        self._add_remote("remote1")
        self._add_remote("remote2")
        pref = self._get_fake_package_refence('whatever/0.1')
        with patch.object(RemoteManager, "get_package_revisions",
                          new=Mock(side_effect=exc)):
            self.client.run(f"list package-revisions {pref} -a -c")
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          There are no matching package references
        remote1:
          ERROR: {output}
        remote2:
          ERROR: {output}
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
          {repr(pref)}#.*""")

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
        self.client.run(f"list package-revisions -a -c {repr(pref)}")
        output = str(self.client.out)
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          {repr(pref)}#.*
        remote1:
          {repr(pref)}#.*
        remote2:
          There are no matching package references""")
        assert bool(re.match(expected_output, output, re.MULTILINE))

    def test_search_in_missing_remote(self):
        remote1 = "remote1"

        remote1_recipe1 = "test_recipe/1.0.0@user/channel"
        remote1_recipe2 = "test_recipe/1.1.0@user/channel"

        expected_output = "No remote 'wrong_remote' defined in remotes"

        self._add_remote(remote1)
        self._upload_recipe(remote1, remote1_recipe1)
        self._upload_recipe(remote1, remote1_recipe2)

        pref = self._get_fake_package_refence(remote1_recipe1)
        self.client.run(f"list package-revisions -r wrong_remote {pref}", assert_error=True)
        assert expected_output in self.client.out
