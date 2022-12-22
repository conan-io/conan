import json
import os
import re
import textwrap
from unittest.mock import Mock, patch

import pytest

from conans.client.remote_manager import RemoteManager
from conans.errors import ConanException, ConanConnectionError
from conans.model.recipe_ref import RecipeReference
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
        self.client.run("remote login {} username -p passwd".format(remote_name))

    def _upload_recipe(self, remote, ref):
        self.client.save({'conanfile.py': GenConanfile()})
        ref = RecipeReference.loads(ref)
        self.client.run(f"create . --name={ref.name} --version={ref.version} "
                        f"--user={ref.user} --channel={ref.channel}")
        self.client.run("upload --force -r {} {}".format(remote, ref))

    def _upload_full_recipe(self, remote, ref):
        self.client.save({"conanfile.py": GenConanfile("pkg", "0.1").with_package_file("file.h",
                                                                                       "0.1")})
        self.client.run("create . --user=user --channel=channel")
        self.client.run("upload --force -r {} {}".format(remote, "pkg/0.1@user/channel"))

        self.client.save({'conanfile.py': GenConanfile().with_require("pkg/0.1@user/channel")
                                                        .with_settings("os", "build_type", "arch")
                                                        .with_option("shared", [True, False])
                                                        .with_default_option("shared", False)
                          })
        self.client.run(f"create . --name={ref.name} --version={ref.version} "
                        f"--user={ref.user} --channel={ref.channel}")
        self.client.run("upload --force -r {} {}".format(remote, ref))

    @staticmethod
    def _get_fake_recipe_refence(recipe_name):
        return f"{recipe_name}#fca0383e6a43348f7989f11ab8f0a92d"

    def _get_lastest_recipe_ref(self, recipe_name):
        return self.client.cache.get_latest_recipe_reference(RecipeReference.loads(recipe_name))


class TestParams(TestListPackageIdsBase):

    @pytest.mark.parametrize("ref", [
        "whatever",
        "whatever/"
    ])
    def test_fail_if_reference_is_not_correct(self, ref):
        self.client.run(f"list {ref}", assert_error=True)
        assert f"ERROR: {ref} is not a valid recipe reference, provide a " \
               f"reference in the form name/version[@user/channel][#RECIPE_REVISION]" \
               in self.client.out

    def test_query_param_is_required(self):
        self._add_remote("remote1")

        self.client.run("list", assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

        self.client.run("list -c", assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

        self.client.run('list -r="*"', assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

        self.client.run("list --remote remote1 --cache", assert_error=True)
        assert "error: the following arguments are required: reference" in self.client.out

    def test_wildcard_not_accepted(self):
        self.client.run('list -r="*" -c test_*', assert_error=True)
        expected_output = "ERROR: test_* is not a valid recipe reference, provide a " \
                          "reference in the form name/version[@user/channel][#RECIPE_REVISION]"
        assert expected_output in self.client.out

    def test_list_python_requires(self):
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("export . --name=tool --version=1.1.1")
        conanfile = textwrap.dedent("""
                   from conan import ConanFile
                   class Pkg(ConanFile):
                       python_requires ="tool/[*]"
                   """)
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . --name foo --version 1.0")
        self.client.run('list foo/1.0#latest')

        expected_output = textwrap.dedent("""\
        Local Cache:
          foo/1.0#b2ab5ffa95e8c5c19a5d1198be33103a:170e82ef3a6bf0bbcda5033467ab9d7805b11d0b
            python_requires:
              tool/1.1.Z
        """)
        assert self.client.out == expected_output

    def test_list_build_requires(self):
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . --name=tool --version=1.1.1")
        conanfile = textwrap.dedent("""
                   from conan import ConanFile
                   class Pkg(ConanFile):
                       def requirements(self):
                           # We set the package_id_mode so it is part of the package_id
                           self.tool_requires("tool/1.1.1", package_id_mode="minor_mode")
                   """)
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . --name foo --version 1.0")
        self.client.run('list foo/1.0#latest')

        expected_output = textwrap.dedent("""\
        Local Cache:
          foo/1.0#75821be6dc510628d538fffb2f00a51f:d01be73a295dca843e5e198334f86ae7038423d7
            build_requires:
              tool/1.1.Z
        """)
        assert self.client.out == expected_output


class TestListPackagesFromRemotes(TestListPackageIdsBase):
    def test_by_default_search_only_in_cache(self):
        self._add_remote("remote1")
        self._add_remote("remote2")

        expected_output = textwrap.dedent("""\
        Local Cache:
          There are no packages""")

        self.client.run(f"list {self._get_fake_recipe_refence('whatever/0.1')}")
        assert expected_output in self.client.out

    def test_search_no_matching_recipes(self):
        self._add_remote("remote1")
        self._add_remote("remote2")

        # TODO: Improve consistency of error messages
        expected_output = textwrap.dedent("""\
        Local Cache:
          There are no packages
        remote1:
          ERROR: Recipe not found: 'whatever/0.1'. [Remote: remote1]
        remote2:
          ERROR: Recipe not found: 'whatever/0.1'. [Remote: remote2]
        """)

        rrev = self._get_fake_recipe_refence('whatever/0.1')
        self.client.run(f'list -c -r="*" {rrev}')
        assert expected_output == self.client.out

    def test_fail_if_no_configured_remotes(self):
        self.client.run('list -r="*" whatever/1.0#123', assert_error=True)
        assert "ERROR: Remotes for pattern '*' can't be found or are disabled" in self.client.out

    def test_search_disabled_remote(self):
        self._add_remote("remote1")
        self._add_remote("remote2")
        self.client.run("remote disable remote1")
        # He have to put both remotes instead of using "-a" because of the
        # disbaled remote won't appear
        self.client.run("list whatever/1.0#123 -r remote1 -r remote2", assert_error=True)
        assert "ERROR: Remote 'remote1' can't be found or is disabled" in self.client.out

    @pytest.mark.parametrize("exc,output", [
        (ConanConnectionError("Review your network!"), "ERROR: Review your network!"),
        (ConanException("Boom!"), "ERROR: Boom!")
    ])
    def test_search_remote_errors_but_no_raising_exceptions(self, exc, output):
        self._add_remote("remote1")
        self._add_remote("remote2")
        rrev = self._get_fake_recipe_refence("whatever/1.0")
        with patch.object(RemoteManager, "search_packages",
                          new=Mock(side_effect=exc)):
            self.client.run(f'list {rrev} -r="*" -c')
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          There are no packages
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
        self.client.run("export . --user=user --channel=channel")
        rrev = self._get_lastest_recipe_ref("test_recipe/1.0.0@user/channel")
        self.client.run(f"list {rrev.repr_notime()}")
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          There are no packages
        """)
        assert expected_output == str(self.client.out)

    @pytest.mark.xfail(reason="conaninfo.txt only stores requires=pkg/0.X now")
    def test_search_with_full_reference(self):
        remote_name = "remote1"
        recipe_name = "test_recipe/1.0.0@user/channel"
        self._add_remote(remote_name)
        self._upload_full_recipe(remote_name, recipe_name)
        rrev = self._get_lastest_recipe_ref(recipe_name)
        self.client.run(f"list -r remote1 {rrev.repr_notime()}")

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
        """ % rrev.repr_notime())
        assert bool(re.match(expected_output, str(self.client.out), re.MULTILINE))

    def test_search_with_full_reference_but_package_has_no_properties(self):
        remote_name = "remote1"
        recipe_name = "test_recipe/1.0.0@user/channel"
        self._add_remote(remote_name)
        self._upload_recipe(remote_name, recipe_name)
        rrev = self._get_lastest_recipe_ref(recipe_name)
        self.client.run(f"list -r remote1 {rrev.repr_notime()}")

        expected_output = textwrap.dedent("""\
        remote1:
          %s:.{40}
        """ % rrev.repr_notime())

        assert bool(re.match(expected_output, str(self.client.out), re.MULTILINE))

    @pytest.mark.xfail(reason="conaninfo.txt only stores requires=pkg/0.X now")
    def test_search_with_reference_without_revision_in_cache_and_remotes(self):
        remote_name = "remote1"
        ref = "test_recipe/1.0.0@user/channel"
        self._add_remote(remote_name)
        self._upload_full_recipe(remote_name, ref)
        self.client.run(f'list -r="*" -c {ref}')
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
        """ % {"rrev": rrev.repr_notime()})

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
        self.client.run(f'list -r="*" -c {rrev.repr_notime()}')
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
          There are no packages
        """ % {"rrev": rrev.repr_notime()})
        assert bool(re.match(expected_output, output, re.MULTILINE))

    def test_search_in_missing_remote(self):
        remote1 = "remote1"

        remote1_recipe1 = "test_recipe/1.0.0@user/channel"
        remote1_recipe2 = "test_recipe/1.1.0@user/channel"

        expected_output = "ERROR: Remote 'wrong_remote' can't be found or is disabled"

        self._add_remote(remote1)
        self._upload_recipe(remote1, remote1_recipe1)
        self._upload_recipe(remote1, remote1_recipe2)

        rrev = self._get_fake_recipe_refence(remote1_recipe1)
        self.client.run(f"list -r wrong_remote {rrev}", assert_error=True)
        assert expected_output in self.client.out


class TestListPackages:
    def test_list_packages(self):
        c = TestClient(default_server_user=True)
        c.save({"dep/conanfile.py": GenConanfile("dep", "1.2.3"),
                "pkg/conanfile.py": GenConanfile("pkg", "2.3.4").with_requires("dep/1.2.3")
                .with_settings("os", "arch").with_shared_option(False)})
        c.run("create dep")
        c.run("create pkg -s os=Windows -s arch=x86")
        # Revision is needed explicitly!
        c.run("list pkg/2.3.4#0fc07368b81b38197adc73ee2cb89da8")
        pref = "pkg/2.3.4#0fc07368b81b38197adc73ee2cb89da8:ec080285423a5e38126f0d5d51b524cf516ff7a5"
        expected = textwrap.dedent(f"""\
            Local Cache:
              {pref}
                settings:
                  arch=x86
                  os=Windows
                options:
                  shared=False
                requires:
                  dep/1.2.Z
            """)
        assert expected == c.out

        c.run("list pkg/2.3.4#0fc07368b81b38197adc73ee2cb89da8 --format=json",
              redirect_stdout="packages.json")
        pkgs_json = c.load("packages.json")
        pkgs_json = json.loads(pkgs_json)
        assert pkgs_json["Local Cache"]["packages"][pref]["settings"]["os"] == "Windows"

    def test_list_conf(self):
        """ test that tools.info.package_id:confs works, affecting the package_id and
        can be listed when we are listing packages
        """
        client = TestClient()
        conanfile = GenConanfile().with_settings("os")
        profile = textwrap.dedent(f"""
            [conf]
            tools.info.package_id:confs=["tools.build:cxxflags", "tools.build:cflags"]
            tools.build:cxxflags=["--flag1", "--flag2"]
            tools.build:cflags+=["--flag3", "--flag4"]
            tools.build:sharedlinkflags=+["--flag5", "--flag6"]
            """)
        client.save({"conanfile.py": conanfile, "profile": profile})
        client.run('create . --name=pkg --version=0.1 -s os=Windows -pr profile')
        client.assert_listed_binary({"pkg/0.1": ("89d32f25195a77f4ae2e77414b870781853bdbc1",
                                                 "Build")})
        revision = client.exported_recipe_revision()
        client.run(f"list pkg/0.1#{revision}")
        assert "tools.build:cxxflags=['--flag1', '--flag2']" in client.out
        assert "tools.build:cflags=['--flag3', '--flag4']" in client.out
        assert "sharedlinkflags" not in client.out


class TestListPackagesHTML:
    def test_list_packages_html(self):
        c = TestClient()
        c.save({"dep/conanfile.py": GenConanfile("dep", "1.2.3"),
                "pkg/conanfile.py": GenConanfile("pkg", "2.3.4").with_requires("dep/1.2.3")
                .with_settings("os", "arch").with_shared_option(False)})
        c.run("create dep")
        c.run("create pkg -s os=Windows -s arch=x86")
        # Revision is needed explicitly!
        c.run("list pkg/2.3.4#latest --format=html", redirect_stdout="table.html")
        table = c.load("table.html")
        assert "<!DOCTYPE html>" in table
        # TODO: The actual good html is missing

    def test_list_packages_html_custom(self):
        """ test that tools.info.package_id:confs works, affecting the package_id and
        can be listed when we are listing packages
        """
        c = TestClient()
        c.save({'lib.py': GenConanfile("lib", "0.1")})
        c.run("create lib.py")
        template_folder = os.path.join(c.cache_folder, 'templates')
        c.save({"list_packages.html": '{{ base_template_path }}'}, path=template_folder)
        c.run("list lib/0.1#latest --format=html")
        assert template_folder in c.stdout
