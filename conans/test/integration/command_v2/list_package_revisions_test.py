import re
import textwrap

import pytest

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
    def test_fail_if_reference_is_not_correct(self):
        self.client.run("list package-revisions whatever", assert_error=True)
        assert "ERROR: Specify the 'name' and the 'version'" in self.client.out

        self.client.run("list package-revisions whatever/", assert_error=True)
        assert "ERROR: Specify the 'name' and the 'version'" in self.client.out

        self.client.run("list package-revisions whatever/1", assert_error=True)
        assert "ERROR: Value provided for package version, '1' (type Version), is too short" in self.client.out

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
        self.client.run("list package-revisions -a whatever/1.0", assert_error=True)
        assert "ERROR: The remotes registry is empty" in self.client.out

    def test_search_disabled_remote(self):
        self._add_remote("remote1")
        self.client.run("remote disable remote1")
        pref = self._get_fake_package_refence('whatever/0.1')
        self.client.run(f"list package-revisions -r remote1 {pref}", assert_error=True)
        expected_output = textwrap.dedent("""\
        remote1
          ERROR: Remote 'remote1' is disabled
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

    def test_wildcard_not_accepted(self):
        remote1 = "remote1"
        remote1_recipe1 = "test_recipe/1.0.0@user/channel"

        expected_output = "is an invalid name. Valid names MUST begin with a letter, number or underscore"

        self._add_remote(remote1)
        self._upload_recipe(remote1, remote1_recipe1)
        self.client.run("list package-revisions -a -c test_*", assert_error=True)

        assert expected_output in self.client.out
