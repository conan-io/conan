import os
import re
import textwrap
import time
from collections import OrderedDict
from unittest.mock import patch, Mock

import pytest

from conans.errors import ConanException, ConanConnectionError
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer
from conans.util.env import environment_update


class TestParamErrors:

    def test_query_param_is_required(self):
        c = TestClient()
        c.run("list", assert_error=True)
        assert "error: the following arguments are required: reference" in c.out

        c.run("list -c", assert_error=True)
        assert "error: the following arguments are required: reference" in c.out

        c.run('list -r="*"', assert_error=True)
        assert "error: the following arguments are required: reference" in c.out

        c.run("list --remote remote1 --cache", assert_error=True)
        assert "error: the following arguments are required: reference" in c.out


@pytest.fixture(scope="module")
def client():
    servers = OrderedDict([("default", TestServer()),
                           ("other", TestServer())])
    c = TestClient(servers=servers, inputs=2*["admin", "password"])
    c.save({
        "zlib.py": GenConanfile("zlib"),
        "zlib_ng.py": GenConanfile("zlib_ng", "1.0.0"),
        "zli.py": GenConanfile("zli", "1.0.0"),
        "zli_rev2.py": GenConanfile("zli", "1.0.0").with_settings("os")
                                                   .with_package_file("f.txt", env_var="MYREV"),
        "zlix.py": GenConanfile("zlix", "1.0.0"),
        "test.py": GenConanfile("test", "1.0").with_requires("zlix/1.0.0")

                                              .with_python_requires("zlix/1.0.0"),
        "conf.py": GenConanfile("conf", "1.0")
    })
    c.run("create zli.py")
    c.run("create zlib.py --version=1.0.0 --user=user --channel=channel")
    c.run("create zlib.py --version=2.0.0 --user=user --channel=channel")
    c.run("create zlix.py")
    c.run("create test.py")
    c.run('create conf.py -c tools.info.package_id:confs="[\'tools.build:cxxflags\']"'
          ' -c tools.build:cxxflags="[\'--flag1\']"')
    c.run("upload * -r=default -c")
    c.run("upload * -r=other -c")

    time.sleep(1.0)
    # We create and upload new revisions later, to avoid timestamp overlaps (low resolution)
    with environment_update({"MYREV": "0"}):
        c.run("create zli_rev2.py -s os=Windows")
        c.run("create zli_rev2.py -s os=Linux")
    c.run("upload * -r=default -c")
    with environment_update({"MYREV": "42"}):
        c.run("create zli_rev2.py -s os=Windows")
    c.run("upload * -r=default -c")
    return c


class TestListRefs:

    @staticmethod
    def check(client, pattern, remote, expected):
        r = "-r=default" if remote else ""
        r_msg = "default" if remote else "Local Cache"
        client.run(f"list {pattern} {r}")
        print(client.out)
        expected = textwrap.indent(expected, "  ")
        expected_output = f"{r_msg}:\n" + expected
        assert bool(re.match(expected_output, str(client.out), re.MULTILINE))

    @pytest.mark.parametrize("remote", [True, False])
    def test_list_recipes(self, client, remote):
        pattern = "z*"
        expected = textwrap.dedent(f"""\
          zli
            zli/1.0.0
          zlib
            zlib/1.0.0@user/channel
            zlib/2.0.0@user/channel
          zlix
            zlix/1.0.0
        """)
        self.check(client, pattern, remote, expected)

    @pytest.mark.parametrize("remote", [True, False])
    @pytest.mark.parametrize("pattern", ["zlib", "zlib/*", "*@user/channel"])
    def test_list_recipe_versions(self, client, pattern, remote):
        expected = textwrap.dedent(f"""\
            zlib
              zlib/1.0.0@user/channel
              zlib/2.0.0@user/channel
            """)
        self.check(client, pattern, remote, expected)

    @pytest.mark.parametrize("remote", [True, False])
    @pytest.mark.parametrize("pattern", ["nomatch", "nomatch*", "nomatch/*"])
    def test_list_recipe_no_match(self, client, pattern, remote):
        if pattern == "nomatch":  # EXACT IS AN ERROR
            expected = "ERROR: Recipe 'nomatch' not found"
        else:
            expected = "There are no matching recipe references"

        self.check(client, pattern, remote, expected)

    @pytest.mark.parametrize("remote", [True, False])
    def test_list_recipe_latest_revision(self, client, remote):
        # by default, when a reference is complete, we show latest recipe revision
        pattern = "zli/1.0.0"
        expected = textwrap.dedent(f"""\
            zli
              zli/1.0.0#b58eeddfe2fd25ac3a105f72836b3360 .*
            """)
        self.check(client, pattern, remote, expected)

    @pytest.mark.parametrize("remote", [True, False])
    def test_list_recipe_all_latest_revision(self, client, remote):
        # we can show the latest revision from several matches, if we add ``#latest``
        pattern = "zlib/*#latest"
        expected = textwrap.dedent(f"""\
            zlib
              zlib/1.0.0@user/channel#ffd4bc45820ddb320ab224685b9ba3fb .*
              zlib/2.0.0@user/channel#ffd4bc45820ddb320ab224685b9ba3fb .*
            """)
        self.check(client, pattern, remote, expected)

    @pytest.mark.parametrize("remote", [True, False])
    def test_list_recipe_several_revision(self, client, remote):
        # we can show the latest revision from several matches, if we add ``#latest``
        pattern = "zli/1.0.0#*"
        expected = textwrap.dedent(f"""\
            zli
              zli/1.0.0#f034dc90894493961d92dd32a9ee3b78 .*
              zli/1.0.0#b58eeddfe2fd25ac3a105f72836b3360 .*
            """)
        self.check(client, pattern, remote, expected)

    @pytest.mark.parametrize("remote", [True, False])
    def test_list_recipe_multiple_revision(self, client, remote):
        pattern = "zli*#*"
        expected = textwrap.dedent(f"""\
          zli
            zli/1.0.0#f034dc90894493961d92dd32a9ee3b78 .*
            zli/1.0.0#b58eeddfe2fd25ac3a105f72836b3360 .*
          zlib
            zlib/1.0.0@user/channel#ffd4bc45820ddb320ab224685b9ba3fb .*
            zlib/2.0.0@user/channel#ffd4bc45820ddb320ab224685b9ba3fb .*
          zlix
            zlix/1.0.0#81f598d1d8648389bb7d0494fffb654e .*
            """)
        self.check(client, pattern, remote, expected)


class TestListPrefs:

    @staticmethod
    def check(client, pattern, remote, expected):
        r = "-r=default" if remote else ""
        r_msg = "default" if remote else "Local Cache"
        client.run(f"list {pattern} {r}")
        print(client.out)
        expected = textwrap.indent(expected, "  ")
        expected_output = f"{r_msg}:\n" + expected
        assert bool(re.match(expected_output, str(client.out), re.MULTILINE))

    @pytest.mark.parametrize("remote", [True, False])
    def test_list_pkg_ids(self, client, remote):
        pattern = "zli/1.0.0:*"
        expected = textwrap.dedent(f"""\
            zli
              zli/1.0.0#b58eeddfe2fd25ac3a105f72836b3360 .*
                PID: 9a4eb3c8701508aa9458b1a73d0633783ecc2270 .*
                  settings:
                    os=Linux
                PID: ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715 .*
                  settings:
                    os=Windows
               """)
        self.check(client, pattern, remote, expected)

    @pytest.mark.parametrize("remote", [True, False])
    def test_list_pkg_ids_confs(self, client, remote):
        pattern = "conf/*:*"
        expected = textwrap.dedent("""\
            conf
              conf/1.0#e4e1703f72ed07c15d73a555ec3a2fa1 .*
                PID: 78c6fa29e8164ce399087ad6067c8f9e2f1c4ad0 .*
                  conf:
                    tools.build:cxxflags=\['--flag1'\]
            """)
        self.check(client, pattern, remote, expected)

    @pytest.mark.parametrize("remote", [True, False])
    def test_list_pkg_ids_requires(self, client, remote):
        pattern = "test/*:*"
        expected = textwrap.dedent("""\
          test
            test/1.0#7df6048d3cb39b75618717987fb96453 .*
              PID: 81d0d9a6851a0208c2bb35fdb34eb156359d939b .*
                requires:
                  zlix/1.Y.Z
                python_requires:
                  zlix/1.0.Z
          """)
        self.check(client, pattern, remote, expected)

    @pytest.mark.parametrize("remote", [True, False])
    def test_list_pkg_ids_all_rrevs(self, client, remote):
        pattern = "zli/1.0.0#*:*"
        expected = textwrap.dedent(f"""\
            zli
              zli/1.0.0#f034dc90894493961d92dd32a9ee3b78 .*
                PID: da39a3ee5e6b4b0d3255bfef95601890afd80709 .*
                  Empty package information
              zli/1.0.0#b58eeddfe2fd25ac3a105f72836b3360 .*
                PID: 9a4eb3c8701508aa9458b1a73d0633783ecc2270 .*
                  settings:
                    os=Linux
                PID: ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715 .*
                  settings:
                    os=Windows
               """)
        self.check(client, pattern, remote, expected)

    @pytest.mark.parametrize("remote", [True, False])
    def test_list_latest_prevs(self, client, remote):
        pattern = "zli/1.0.0:*#latest"
        expected = textwrap.dedent(f"""\
            zli
              zli/1.0.0#b58eeddfe2fd25ac3a105f72836b3360 .*
                PID: 9a4eb3c8701508aa9458b1a73d0633783ecc2270
                  PREV: 9beff32b8c94ea0ce5a5e67dad95f525 .*
                PID: ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715
                  PREV: d9b1e9044ee265092e81db7028ae10e0 .*
            """)
        self.check(client, pattern, remote, expected)

    @pytest.mark.parametrize("remote", [True, False])
    def test_list_all_prevs(self, client, remote):
        pattern = "zli/1.0.0:*#*"
        # TODO: We might want to improve the output, grouping PREVS for the
        #  same package_id
        expected = textwrap.dedent(f"""\
          zli
            zli/1.0.0#b58eeddfe2fd25ac3a105f72836b3360 .*
              PID: 9a4eb3c8701508aa9458b1a73d0633783ecc2270
                PREV: 9beff32b8c94ea0ce5a5e67dad95f525 .*
              PID: ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715
                PREV: d9b1e9044ee265092e81db7028ae10e0 .*
              PID: ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715
                PREV: 24532a030b4fcdfed699511f6bfe35d3 .*
          """)
        self.check(client, pattern, remote, expected)

    @pytest.mark.parametrize("remote", [True, False])
    def test_list_package_id_all_prevs(self, client, remote):
        pattern = "zli/1.0.0:ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715#*"
        # TODO: We might want to improve the output, grouping PREVS for the
        #  same package_id
        expected = textwrap.dedent(f"""\
          zli
            zli/1.0.0#b58eeddfe2fd25ac3a105f72836b3360 .*
              PID: ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715
                PREV: d9b1e9044ee265092e81db7028ae10e0 .*
              PID: ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715
                PREV: 24532a030b4fcdfed699511f6bfe35d3 .*
          """)
        self.check(client, pattern, remote, expected)

    @pytest.mark.parametrize("remote", [True, False])
    def test_list_package_id_latest_prev(self, client, remote):
        pattern = "zli/1.0.0:ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715"
        expected = textwrap.dedent(f"""\
          zli
            zli/1.0.0#b58eeddfe2fd25ac3a105f72836b3360 .*
              PID: ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715
                PREV: d9b1e9044ee265092e81db7028ae10e0 .*
          """)
        self.check(client, pattern, remote, expected)

    @pytest.mark.parametrize("remote", [True, False])
    def test_list_missing_package_id(self, client, remote):
        pattern = "zli/1.0.0:nonexists_id"
        # TODO: The message is still different in the server
        expected = textwrap.dedent(f"""\
            ERROR: Binary package not found: 'zli/1.0.0.*
            """)
        self.check(client, pattern, remote, expected)

    def test_query(self):
        pass


class TestListRemotes:
    """ advanced use case:
    - check multiple remotes output
    """

    def test_search_no_matching_recipes(self, client):
        expected_output = textwrap.dedent("""\
        Local Cache:
          ERROR: Recipe 'whatever/0.1' not found
        default:
          ERROR: Recipe 'whatever/0.1' not found
        other:
          ERROR: Recipe 'whatever/0.1' not found
        """)

        client.run('list -c -r="*" whatever/0.1')
        assert expected_output == client.out

    def test_fail_if_no_configured_remotes(self):
        client = TestClient()
        client.run('list -r="*" whatever/1.0#123', assert_error=True)
        assert "ERROR: Remotes for pattern '*' can't be found or are disabled" in client.out

    @pytest.mark.parametrize("exc,output", [
        (ConanConnectionError("Review your network!"), "ERROR: Review your network!"),
        (ConanException("Boom!"), "ERROR: Boom!")
    ])
    def test_search_remote_errors_but_no_raising_exceptions(self, client, exc, output):
        with patch("conan.api.subapi.search.SearchAPI.recipes", new=Mock(side_effect=exc)):
            client.run(f'list whatever/1.0 -r="*"')
        expected_output = textwrap.dedent(f"""\
            default:
              {output}
            other:
              {output}
            """)
        assert expected_output == client.out


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
