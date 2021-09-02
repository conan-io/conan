import re
import textwrap
from unittest.mock import Mock, patch

import pytest

from conans.client.remote_manager import RemoteManager
from conans.errors import ConanException, ConanConnectionError
from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer


class TestListPackageIdsBase:
    @pytest.fixture(autouse=True)
    def _setup(self):
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

    def _upload_full_recipe(self, remote, reference):
        self.client.save({"conanfile.py": GenConanfile("pkg", "0.1").with_package_file("file.h", "0.1")})
        self.client.run("create . user/channel")
        self.client.run("upload --force --all -r {} {}".format(remote, "pkg/0.1@user/channel"))

        self.client.save({'conanfile.py': GenConanfile().with_require("pkg/0.1@user/channel")
                                                        .with_settings("os", "build_type", "arch")
                                                        .with_option("shared", [True, False])
                                                        .with_default_option("shared", False)
                          })
        self.client.run("create . {}".format(reference))
        self.client.run("upload --force --all -r {} {}".format(remote, reference))

    @staticmethod
    def _get_fake_recipe_refence(recipe_name):
        return f"{recipe_name}#fca0383e6a43348f7989f11ab8f0a92d"

    def _get_lastest_recipe_ref(self, recipe_name):
        return self.client.cache.get_latest_rrev(ConanFileReference.loads(recipe_name))


class TestParams(TestListPackageIdsBase):

    @pytest.mark.parametrize("ref", [
        "whatever",
        "whatever/",
        "whatever/1"
    ])
    def test_fail_if_reference_is_not_correct(self, ref):
        self.client.run(f"list package-ids {ref}", assert_error=True)
        assert f"ERROR: {ref} is not a valid recipe reference, provide a " \
               f"reference in the form name/version[@user/channel][#RECIPE_REVISION]" in self.client.out

    def test_query_param_is_required(self):
        self._add_remote("remote1")

        self.client.run("list package-ids", assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

        self.client.run("list package-ids -c", assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

        self.client.run("list package-ids --all-remotes", assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

        self.client.run("list package-ids --remote remote1 --cache", assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

    def test_remote_and_all_remotes_are_mutually_exclusive(self):
        self._add_remote("remote1")

        self.client.run("list package-ids --all-remotes --remote remote1 package/1.0", assert_error=True)
        assert "error: argument -r/--remote: not allowed with argument -a/--all-remotes" in self.client.out

    def test_wildcard_not_accepted(self):
        self.client.run("list package-ids -a -c test_*", assert_error=True)
        expected_output = "ERROR: test_* is not a valid recipe reference, provide a " \
                          "reference in the form name/version[@user/channel][#RECIPE_REVISION]"
        assert expected_output in self.client.out


class TestListPackagesFromRemotes(TestListPackageIdsBase):
    def test_by_default_search_only_in_cache(self):
        self._add_remote("remote1")
        self._add_remote("remote2")

        expected_output = textwrap.dedent("""\
        Local Cache:
          There are no matching recipe references
        """)

        self.client.run(f"list package-ids {self._get_fake_recipe_refence('whatever/0.1')}")
        assert expected_output == self.client.out

    def test_search_no_matching_recipes(self):
        self._add_remote("remote1")
        self._add_remote("remote2")

        expected_output = textwrap.dedent("""\
        Local Cache:
          There are no matching recipe references
        remote1:
          There are no matching recipe references
        remote2:
          There are no matching recipe references
        """)

        rrev = self._get_fake_recipe_refence('whatever/0.1')
        self.client.run(f"list package-ids -c -a {rrev}")
        assert expected_output == self.client.out

    def test_fail_if_no_configured_remotes(self):
        self.client.run("list package-ids -a whatever/1.0", assert_error=True)
        assert "ERROR: The remotes registry is empty" in self.client.out

    def test_search_disabled_remote(self):
        self._add_remote("remote1")
        self._add_remote("remote2")
        self.client.run("remote disable remote1")
        # He have to put both remotes instead of using "-a" because of the
        # disbaled remote won't appear
        self.client.run("list package-ids whatever/1.0 -r remote1 -r remote2")
        expected_output = textwrap.dedent("""\
        remote1:
          ERROR: Remote 'remote1' is disabled
        remote2:
          There are no matching recipe references
        """)
        assert expected_output == self.client.out

    @pytest.mark.parametrize("exc,output", [
        (ConanConnectionError("Review your network!"),
         "ERROR: Review your network!"),
        (ConanException("Boom!"), "ERROR: Boom!")
    ])
    def test_search_remote_errors_but_no_raising_exceptions(self, exc, output):
        self._add_remote("remote1")
        self._add_remote("remote2")
        rrev = self._get_fake_recipe_refence("whatever/1.0")
        with patch.object(RemoteManager, "search_packages",
                          new=Mock(side_effect=exc)):
            self.client.run(f"list package-ids {rrev} -a -c")
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          There are no matching recipe references
        remote1:
          {output}
        remote2:
          {output}
        """)
        assert expected_output == self.client.out


class TestRemotes(TestListPackageIdsBase):

    def test_search_with_full_reference_but_no_packages_in_cache(self):
        self.client.save({
            "conanfile.py": GenConanfile("test_recipe", "1.0.0").with_package_file("file.h", "0.1")
        })
        self.client.run("export . user/channel")
        rrev = self._get_lastest_recipe_ref("test_recipe/1.0.0@user/channel")
        self.client.run(f"list package-ids {repr(rrev)}")
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          There are no matching recipe references
        """)
        assert expected_output == str(self.client.out)

    @pytest.mark.xfail(reason="conaninfo.txt only stores requires=pkg/0.X now")
    def test_search_with_full_reference(self):
        remote_name = "remote1"
        recipe_name = "test_recipe/1.0.0@user/channel"
        self._add_remote(remote_name)
        self._upload_full_recipe(remote_name, recipe_name)
        rrev = self._get_lastest_recipe_ref(recipe_name)
        self.client.run(f"list package-ids -r remote1 {repr(rrev)}")

        expected_output = textwrap.dedent("""\
        remote1:
          %s:.{40}
            settings:
              arch=.*
              build_type=.*
              os=.*
            options:
              shared=False
            requires:
              pkg/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9
        """ % repr(rrev))
        assert bool(re.match(expected_output, str(self.client.out), re.MULTILINE))

    def test_search_with_full_reference_but_package_has_no_properties(self):
        remote_name = "remote1"
        recipe_name = "test_recipe/1.0.0@user/channel"
        self._add_remote(remote_name)
        self._upload_recipe(remote_name, recipe_name)
        rrev = self._get_lastest_recipe_ref(recipe_name)
        self.client.run(f"list package-ids -r remote1 {repr(rrev)}")

        expected_output = textwrap.dedent("""\
        remote1:
          %s:.{40}
        """ % repr(rrev))

        assert bool(re.match(expected_output, str(self.client.out), re.MULTILINE))

    @pytest.mark.xfail(reason="conaninfo.txt only stores requires=pkg/0.X now")
    def test_search_with_reference_without_revision_in_cache_and_remotes(self):
        remote_name = "remote1"
        ref = "test_recipe/1.0.0@user/channel"
        self._add_remote(remote_name)
        self._upload_full_recipe(remote_name, ref)
        self.client.run(f"list package-ids -a -c {ref}")
        # Now, let's check that we're using the latest one by default
        rrev = self._get_lastest_recipe_ref(ref)
        expected_output = textwrap.dedent("""\
        Local Cache:
          %(rrev)s:.{40}
            settings:
              arch=.*
              build_type=.*
              os=.*
            options:
              shared=False
            requires:
              pkg/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9
        remote1:
          %(rrev)s:.{40}
            settings:
              arch=.*
              build_type=.*
              os=.*
            options:
              shared=False
            requires:
              pkg/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9
        """ % {"rrev": repr(rrev)})

        assert bool(re.match(expected_output, str(self.client.out), re.MULTILINE))

    @pytest.mark.xfail(reason="conaninfo.txt only stores requires=pkg/0.X now")
    def test_search_in_all_remotes_and_cache(self):
        remote1 = "remote1"
        remote2 = "remote2"

        self._add_remote(remote1)
        self._upload_full_recipe(remote1, "test_recipe/1.0.0@user/channel")
        self._upload_full_recipe(remote1, "test_recipe/1.1.0@user/channel")

        self._add_remote(remote2)
        self._upload_full_recipe(remote2, "test_recipe/2.0.0@user/channel")
        self._upload_full_recipe(remote2, "test_recipe/2.1.0@user/channel")

        # Getting the latest recipe ref
        rrev = self._get_lastest_recipe_ref("test_recipe/1.0.0@user/channel")
        self.client.run(f"list package-ids -a -c {repr(rrev)}")
        output = str(self.client.out)
        expected_output = textwrap.dedent("""\
        Local Cache:
          %(rrev)s:.{40}
            settings:
              arch=.*
              build_type=.*
              os=.*
            options:
              shared=False
            requires:
              pkg/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9
        remote1:
          %(rrev)s:.{40}
            settings:
              arch=.*
              build_type=.*
              os=.*
            options:
              shared=False
            requires:
              pkg/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9
        remote2:
          There are no matching recipe references
        """ % {"rrev": repr(rrev)})
        assert bool(re.match(expected_output, output, re.MULTILINE))

    def test_search_in_missing_remote(self):
        remote1 = "remote1"

        remote1_recipe1 = "test_recipe/1.0.0@user/channel"
        remote1_recipe2 = "test_recipe/1.1.0@user/channel"

        expected_output = "No remote 'wrong_remote' defined in remotes"

        self._add_remote(remote1)
        self._upload_recipe(remote1, remote1_recipe1)
        self._upload_recipe(remote1, remote1_recipe2)

        rrev = self._get_fake_recipe_refence(remote1_recipe1)
        self.client.run(f"list package-ids -r wrong_remote {rrev}", assert_error=True)
        assert expected_output in self.client.out
