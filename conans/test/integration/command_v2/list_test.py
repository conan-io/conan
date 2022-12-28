import json
import os
import re
import textwrap
from unittest.mock import patch, Mock

import pytest

from conans.errors import ConanException, ConanConnectionError
from conans.model.recipe_ref import RecipeReference
from conans.model.package_ref import PkgReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer


class TestListBase:
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
                        f"-s os=Macos -s build_type=Release -s arch=x86_64 "
                        f"--user={ref.user} --channel={ref.channel}")
        self.client.run("upload --force -r {} {}".format(remote, ref))

    def _upload_full_recipe_without_conaninfo(self, remote, ref):
        self.client.save({"conanfile.py": GenConanfile("pkg", "0.1").with_package_file("file.h",
                                                                                       "0.1")})
        self.client.run("create . --user=user --channel=channel")
        self.client.run("upload --force -r {} {}".format(remote, "pkg/0.1@user/channel"))

        self.client.save({'conanfile.py': GenConanfile()
                          })
        self.client.run(f"create . --name={ref.name} --version={ref.version} "
                        f"-s os=Macos -s build_type=Release -s arch=x86_64 "
                        f"--user={ref.user} --channel={ref.channel}")
        self.client.run("upload --force -r {} {}".format(remote, ref))


    @staticmethod
    def _get_fake_recipe_refence(recipe_name):
        return f"{recipe_name}#fca0383e6a43348f7989f11ab8f0a92d"

    def _get_lastest_recipe_ref(self, recipe_name):
        return self.client.cache.get_latest_recipe_reference(RecipeReference.loads(recipe_name))

    def _get_lastest_package_ref(self, pref):
        return self.client.cache.get_latest_package_reference(PkgReference.loads(pref))


class TestParams(TestListBase):

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


class TestRemotes(TestListBase):
    def test_by_default_search_only_in_cache(self):
        self._add_remote("remote1")
        self._add_remote("remote2")

        expected_output = textwrap.dedent("""\
        Local Cache:
          ERROR: Recipe 'whatever/0.1' not found""")

        self.client.run(f"list {self._get_fake_recipe_refence('whatever/0.1')}")
        assert expected_output in self.client.out

    def test_search_no_matching_recipes(self):
        self._add_remote("remote1")
        self._add_remote("remote2")

        expected_output = textwrap.dedent("""\
        Local Cache:
          ERROR: Recipe 'whatever/0.1' not found
        remote1:
          ERROR: Recipe 'whatever/0.1' not found
        remote2:
          ERROR: Recipe 'whatever/0.1' not found
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
        with patch("conan.api.subapi.search.SearchAPI.recipes", new=Mock(side_effect=exc)):
            self.client.run(f'list whatever/1.0 -r="*"')
        expected_output = textwrap.dedent(f"""\
        remote1:
          {output}
        remote2:
          {output}
        """)
        assert expected_output == self.client.out

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


class TestListUseCases(TestListBase):

    def test_list_recipes(self):
        self.client.save({
            "zlib.py": GenConanfile("zlib", "1.0.0"),
            "zlib2.py": GenConanfile("zlib", "2.0.0"),
            "zli.py": GenConanfile("zli", "1.0.0"),
            "zlix.py": GenConanfile("zlix", "1.0.0"),
        })
        self.client.run("export zlib.py --user=user --channel=channel")
        self.client.run("export zlib2.py --user=user --channel=channel")
        self.client.run("export zli.py")
        self.client.run("export zlix.py")
        self.client.run(f"list z*")
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          zlix
            zlix/1.0.0
          zli
            zli/1.0.0
          zlib
            zlib/2.0.0@user/channel
            zlib/1.0.0@user/channel
        """)
        assert expected_output == self.client.out

    def test_list_latest_recipe_revision_by_default(self):
        self.client.save({
            "conanfile.py": GenConanfile("test_recipe", "1.0.0").with_package_file("file.h", "0.1")
        })
        self.client.run("export . --user=user --channel=channel")
        rrev = self._get_lastest_recipe_ref("test_recipe/1.0.0@user/channel")
        self.client.run(f"list test_recipe/1.0.0@user/channel")
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          test_recipe
            %s .*
        """ % rrev.repr_notime())
        assert bool(re.match(expected_output, str(self.client.out), re.MULTILINE))

    def test_list_all_the_latest_recipe_revision(self):
        self.client.save({
            "hello1.py": GenConanfile("hello", "1.0.0").with_generator("CMakeToolchain"),  # rrev
            "hello.py": GenConanfile("hello", "1.0.0"),  # latest rrev
            "bye.py": GenConanfile("bye", "1.0.0")
        })
        self.client.run("export hello1.py --user=user --channel=channel")
        self.client.run("export hello.py --user=user --channel=channel")
        hello_latest_rrev = self._get_lastest_recipe_ref("hello/1.0.0@user/channel")
        self.client.run("export bye.py --user=user --channel=channel")
        self.client.run(f"list *#latest")
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          bye
            bye/1.0.0@user/channel#c720a82a9c904a0450ec1aa177281ea2 .*
          hello
            hello/1.0.0@user/channel#7a34833afbd87d791b2201882b1afb2b .*
        """)
        assert bool(re.match(expected_output, str(self.client.out), re.MULTILINE))
        assert hello_latest_rrev.repr_notime() in expected_output

    def test_list_latest_package_revisions_by_default(self):
        self.client.save({
            "conanfile.py": GenConanfile("test_recipe", "1.0.0").with_package_file("file.h", "0.1")
        })
        self.client.run("create . --user=user --channel=channel")
        rrev = self._get_lastest_recipe_ref("test_recipe/1.0.0@user/channel")
        pid = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
        prev = self._get_lastest_package_ref(f"{rrev.repr_notime()}:{pid}")
        self.client.run(f"list {prev.repr_notime()}")
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          test_recipe
            test_recipe/1.0.0@user/channel#ddfadce26d00a560850eb8767fe76ae4 .*
              PID: da39a3ee5e6b4b0d3255bfef95601890afd80709
                PREV: 9c929aed65f04337a4143311d72fc897 .*
        """)
        assert bool(re.match(expected_output, str(self.client.out), re.MULTILINE))

    def test_list_all_the_latest_package_revisions(self):
        self.client.save({
            "hello.py": GenConanfile("hello", "1.0.0").with_package_file("file.h", "0.1"),
            "bye.py": GenConanfile("bye", "1.0.0").with_package_file("file.h", "0.1")
        })
        self.client.run("create hello.py --user=user --channel=channel")
        self.client.run("create hello.py --user=user --channel=channel")  # latest prev
        self.client.run("create bye.py --user=user --channel=channel")
        self.client.run("create bye.py --user=user --channel=channel")   # latest prev
        self.client.run("list *:*#latest")
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          bye
            bye/1.0.0@user/channel#51edd97e27e407a01be830282558c32a .*
              PID: da39a3ee5e6b4b0d3255bfef95601890afd80709
                PREV: 9c929aed65f04337a4143311d72fc897 .*
          hello
            hello/1.0.0@user/channel#6fccfa5dd0bbb1223578c1771839eb6d .*
              PID: da39a3ee5e6b4b0d3255bfef95601890afd80709
                PREV: 9c929aed65f04337a4143311d72fc897 .*
        """)
        assert bool(re.match(expected_output, str(self.client.out), re.MULTILINE))

    def test_search_package_ids_but_empty_conan_info(self):
        remote_name = "remote1"
        recipe_name = "test_recipe/1.0.0@user/channel"
        self._add_remote(remote_name)
        self._upload_recipe(remote_name, recipe_name)
        rrev = self._get_lastest_recipe_ref(recipe_name)
        self.client.run(f"list {rrev.repr_notime()}:* -r remote1")
        expected_output = textwrap.dedent("""\
        remote1:
          test_recipe
            test_recipe/1.0.0@user/channel#4d670581ccb765839f2239cc8dff8fbd .*
              PID: da39a3ee5e6b4b0d3255bfef95601890afd80709
                Empty package information
        """)
        assert bool(re.match(expected_output, str(self.client.out), re.MULTILINE))

    def test_search_package_ids_from_latest_rrev_in_all_remotes_and_cache(self):
        remote1 = "remote1"
        remote2 = "remote2"

        self._add_remote(remote1)
        self._upload_full_recipe(remote1, RecipeReference(name="test_recipe", version="1.0",
                                                          user="user", channel="channel"))
        self._add_remote(remote2)
        self._upload_full_recipe(remote2, RecipeReference(name="test_recipe", version="2.1",
                                                          user="user", channel="channel"))
        self.client.run(f'list test_recipe/*:* -r="*" -c')
        output = str(self.client.out)
        expected_output = textwrap.dedent("""\
        Local Cache:
          test_recipe
            test_recipe/2.1@user/channel#a22316c3831b70763e4405841ee93f27 .*
              PID: 630ddee056279fad89b691ac0f36eb084f40da38 .*
                settings:
                  arch=x86_64
                  build_type=Release
                  os=Macos
                options:
                  shared=False
                requires:
                  pkg/0.1.Z@user/channel
            test_recipe/1.0@user/channel#a22316c3831b70763e4405841ee93f27 .*
              PID: 630ddee056279fad89b691ac0f36eb084f40da38 .*
                settings:
                  arch=x86_64
                  build_type=Release
                  os=Macos
                options:
                  shared=False
                requires:
                  pkg/0.1.Z@user/channel
        remote1:
          test_recipe
            test_recipe/1.0@user/channel#a22316c3831b70763e4405841ee93f27 .*
              PID: 630ddee056279fad89b691ac0f36eb084f40da38
                settings:
                  arch=x86_64
                  build_type=Release
                  os=Macos
                options:
                  shared=False
                requires:
                  pkg/0.1.Z@user/channel
        remote2:
          test_recipe
            test_recipe/2.1@user/channel#a22316c3831b70763e4405841ee93f27 .*
              PID: 630ddee056279fad89b691ac0f36eb084f40da38
                settings:
                  arch=x86_64
                  build_type=Release
                  os=Macos
                options:
                  shared=False
                requires:
                  pkg/0.1.Z@user/channel
        """)
        assert bool(re.match(expected_output, output, re.MULTILINE))

    def test_search_all_revisions_and_package_revisions(self):
        """Checking if RREVs and PREVs are shown correctly"""
        remote1 = "remote1"
        remote2 = "remote2"

        self._add_remote(remote1)
        self._upload_full_recipe_without_conaninfo(remote1,
                                                   RecipeReference(name="test_recipe", version="1.0",
                                                                   user="user", channel="channel"))
        self._add_remote(remote2)
        self._upload_full_recipe_without_conaninfo(remote2,
                                                   RecipeReference(name="test_recipe", version="2.1",
                                                                   user="user", channel="channel"))
        self.client.run(f'list *#* -r="*" -c')
        output = str(self.client.out)
        expected_output = textwrap.dedent("""\
        Local Cache:
          test_recipe
            test_recipe/2.1@user/channel#4d670581ccb765839f2239cc8dff8fbd .*
            test_recipe/1.0@user/channel#4d670581ccb765839f2239cc8dff8fbd .*
          pkg
            pkg/0.1@user/channel#44a36b797bc85fb66af6acf90cf8f539 .*
        remote1:
          pkg
            pkg/0.1@user/channel#44a36b797bc85fb66af6acf90cf8f539 .*
          test_recipe
            test_recipe/1.0@user/channel#4d670581ccb765839f2239cc8dff8fbd .*
        remote2:
          pkg
            pkg/0.1@user/channel#44a36b797bc85fb66af6acf90cf8f539 .*
          test_recipe
            test_recipe/2.1@user/channel#4d670581ccb765839f2239cc8dff8fbd .*
        """)
        assert bool(re.match(expected_output, output, re.MULTILINE))
        self.client.run(f'list test_recipe/*:*#* -r="*" -c')
        output = str(self.client.out)
        expected_output = textwrap.dedent("""\
        Local Cache:
          test_recipe
            test_recipe/2.1@user/channel#4d670581ccb765839f2239cc8dff8fbd .*
              PID: da39a3ee5e6b4b0d3255bfef95601890afd80709
                PREV: 0ba8627bd47edc3a501e8f0eb9a79e5e .*
            test_recipe/1.0@user/channel#4d670581ccb765839f2239cc8dff8fbd .*
              PID: da39a3ee5e6b4b0d3255bfef95601890afd80709
                PREV: 0ba8627bd47edc3a501e8f0eb9a79e5e .*
        remote1:
          test_recipe
            test_recipe/1.0@user/channel#4d670581ccb765839f2239cc8dff8fbd .*
              PID: da39a3ee5e6b4b0d3255bfef95601890afd80709
                PREV: 0ba8627bd47edc3a501e8f0eb9a79e5e .*
        remote2:
          test_recipe
            test_recipe/2.1@user/channel#4d670581ccb765839f2239cc8dff8fbd .*
              PID: da39a3ee5e6b4b0d3255bfef95601890afd80709
                PREV: 0ba8627bd47edc3a501e8f0eb9a79e5e .*
        """)
        assert bool(re.match(expected_output, output, re.MULTILINE))

    def test_search_all_revisions_given_a_package_id(self):
        """
        Checking if PREVs are shown correctly given a PkgID and even though that package has no
        configuration at all.
        """
        remote1 = "remote1"
        self._add_remote(remote1)
        self._upload_full_recipe_without_conaninfo(remote1,
                                                   RecipeReference(name="test_recipe", version="1.0",
                                                                   user="user", channel="channel"))
        self.client.run(f'list *:* -r=remote1')
        output = str(self.client.out)
        expected_output = textwrap.dedent("""\
        remote1:
          pkg
            pkg/0.1@user/channel#44a36b797bc85fb66af6acf90cf8f539 .*
              PID: da39a3ee5e6b4b0d3255bfef95601890afd80709
                Empty package information
          test_recipe
            test_recipe/1.0@user/channel#4d670581ccb765839f2239cc8dff8fbd .*
              PID: da39a3ee5e6b4b0d3255bfef95601890afd80709
                Empty package information
        """)
        assert bool(re.match(expected_output, output, re.MULTILINE))
        self.client.run(f'list test_recipe/*:da39a3ee5e6b4b0d3255bfef95601890afd80709#* -r=remote1')
        output = str(self.client.out)
        expected_output = textwrap.dedent("""\
        remote1:
          test_recipe
            test_recipe/1.0@user/channel#4d670581ccb765839f2239cc8dff8fbd .*
              PID: da39a3ee5e6b4b0d3255bfef95601890afd80709
                PREV: 0ba8627bd47edc3a501e8f0eb9a79e5e .*
        """)
        assert bool(re.match(expected_output, output, re.MULTILINE))

    def test_list_package_query_options(self):
        self.client.save({"conanfile.py": GenConanfile("pkg", "0.1")
                                          .with_package_file("file.h", "0.1")
                                          .with_settings("os", "build_type", "arch")})
        self.client.run("create . --user=user --channel=channel "
                        "-s os=Windows -s build_type=Release -s arch=x86_64")
        self.client.run("create . --user=user --channel=channel "
                        "-s os=Macos -s build_type=Release -s arch=x86_64")
        self.client.run("create . --user=user --channel=channel "
                        "-s os=Macos -s build_type=Release -s arch=armv7")
        self.client.run(f'list pkg/0.1#*:*')
        output = str(self.client.out)
        expected_output = textwrap.dedent("""\
        Local Cache:
          pkg
            pkg/0.1@user/channel#89ab3ffd306cb65a8ca8e2a1c8b96aae .*
              PID: 5f2a74726e897f644b3f42dea59faecf8eee2b50 .*
                settings:
                  arch=armv7
                  build_type=Release
                  os=Macos
              PID: 723257509aee8a72faf021920c2874abc738e029 .*
                settings:
                  arch=x86_64
                  build_type=Release
                  os=Windows
              PID: 9ac8640923e5284645f8852ef8ba335654f4020e .*
                settings:
                  arch=x86_64
                  build_type=Release
                  os=Macos
        """)
        assert bool(re.match(expected_output, output, re.MULTILINE))
        self.client.run(f'list pkg/0.1#*:* -p os=Windows')
        output = str(self.client.out)
        expected_output = textwrap.dedent("""\
        Local Cache:
          pkg
            pkg/0.1@user/channel#89ab3ffd306cb65a8ca8e2a1c8b96aae .*
              PID: 723257509aee8a72faf021920c2874abc738e029 .*
                settings:
                  arch=x86_64
                  build_type=Release
                  os=Windows
        """)
        assert bool(re.match(expected_output, output, re.MULTILINE))


class TestListPackages:
    def test_list_package_info_and_json_format(self):
        c = TestClient(default_server_user=True)
        c.save({"dep/conanfile.py": GenConanfile("dep", "1.2.3"),
                "pkg/conanfile.py": GenConanfile("pkg", "2.3.4").with_requires("dep/1.2.3")
                .with_settings("os", "arch").with_shared_option(False)})
        c.run("create dep")
        c.run("create pkg -s os=Windows -s arch=x86")
        c.run("list pkg/2.3.4#0fc07368b81b38197adc73ee2cb89da8")
        expected_output = textwrap.dedent(f"""\
        Local Cache:
          pkg
            pkg/2.3.4#0fc07368b81b38197adc73ee2cb89da8 .*
              PID: ec080285423a5e38126f0d5d51b524cf516ff7a5 .*
                settings:
                  arch=x86
                  os=Windows
                options:
                  shared=False
                requires:
                  dep/1.2.Z
        """)
        assert bool(re.match(expected_output, c.out, re.MULTILINE))

        rrev = "pkg/2.3.4#0fc07368b81b38197adc73ee2cb89da8"
        c.run(f"list {rrev} --format=json", redirect_stdout="packages.json")
        pkgs_json = c.load("packages.json")
        pkgs_json = json.loads(pkgs_json)
        pref = "pkg/2.3.4#0fc07368b81b38197adc73ee2cb89da8:ec080285423a5e38126f0d5d51b524cf516ff7a5"
        assert pkgs_json["Local Cache"][rrev][pref]["settings"]["os"] == "Windows"

    def test_list_packages_with_conf(self):
        """Test that tools.info.package_id:confs works, affecting the package_id and
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
        expected_output = textwrap.dedent("""\
        Local Cache:
          pkg
            pkg/0.1#db6569e42e3e9916209e2ef64d6a7b52 .*
              PID: 89d32f25195a77f4ae2e77414b870781853bdbc1 .*
                settings:
                  os=Windows
                conf:
                  tools.build:cflags=\['--flag3', '--flag4'\]
                  tools.build:cxxflags=\['--flag1', '--flag2'\]
        """)
        assert bool(re.match(expected_output, client.out, re.MULTILINE))

    def test_list_packages_python_requires(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=tool --version=1.1.1")
        conanfile = textwrap.dedent("""
                   from conan import ConanFile
                   class Pkg(ConanFile):
                       python_requires ="tool/[*]"
                   """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name foo --version 1.0")
        client.run('list foo/1.0:*')

        expected_output = textwrap.dedent("""\
        Local Cache:
          foo
            foo/1.0#b2ab5ffa95e8c5c19a5d1198be33103a .*
              PID: 170e82ef3a6bf0bbcda5033467ab9d7805b11d0b .*
                python_requires:
                  tool/1.1.Z
        """)
        assert bool(re.match(expected_output, client.out, re.MULTILINE))

    def test_list_packages_build_requires(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=tool --version=1.1.1")
        conanfile = textwrap.dedent("""
                   from conan import ConanFile
                   class Pkg(ConanFile):
                       def requirements(self):
                           # We set the package_id_mode so it is part of the package_id
                           self.tool_requires("tool/1.1.1", package_id_mode="minor_mode")
                   """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name foo --version 1.0")
        client.run('list foo/1.0:*')

        expected_output = textwrap.dedent("""\
        Local Cache:
          foo
            foo/1.0#75821be6dc510628d538fffb2f00a51f .*
              PID: d01be73a295dca843e5e198334f86ae7038423d7 .*
                build_requires:
                  tool/1.1.Z
        """)
        assert bool(re.match(expected_output, client.out, re.MULTILINE))


class TestListHTML:
    def test_list_html(self):
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

    def test_list_html_custom(self):
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
