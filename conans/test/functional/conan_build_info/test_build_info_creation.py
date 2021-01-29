import json
import os
import sys
import textwrap
import unittest

import pytest
from mock import patch, Mock
from six import StringIO

from conans.client.cache.cache import ClientCache
from conans.model.graph_lock import LOCKFILE
from conans.build_info.command import run
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestServer
from conans.test.utils.mocks import TestBufferConanOutput


class MyBuildInfoCreation(unittest.TestCase):
    @patch("conans.build_info.build_info.ClientCache")
    def test_build_info_start(self, mock_cache):
        conan_user_home = temp_folder(True)
        mock_cache.return_value = ClientCache(os.path.join(conan_user_home, ".conan"),
                                              TestBufferConanOutput())
        sys.argv = ["conan_build_info", "--v2", "start", "MyBuildName", "42"]
        run()
        with open(mock_cache.return_value.artifacts_properties_path) as f:
            content = f.read()
            self.assertIn("MyBuildName", content)
            self.assertIn("42", content)

    @patch("conans.build_info.build_info.ClientCache")
    def test_build_info_stop(self, mock_cache):
        conan_user_home = temp_folder(True)
        mock_cache.return_value = ClientCache(os.path.join(conan_user_home, ".conan"),
                                              TestBufferConanOutput())
        sys.argv = ["conan_build_info", "--v2", "stop"]
        run()
        with open(mock_cache.return_value.artifacts_properties_path) as f:
            content = f.read()
            self.assertEqual("", content)

    def mock_response(url, data=None, **kwargs):
        mock_resp = Mock()
        mock_resp.status_code = 204
        if "api/build" in url:
            mock_resp.status_code = 204
        if kwargs.get("auth", None) and (
                kwargs["auth"][0] != "user" or kwargs["auth"][1] != "password"):
            mock_resp.status_code = 401
        elif (kwargs["headers"].get("X-JFrog-Art-Api", None) and
                kwargs["headers"]["X-JFrog-Art-Api"] != "apikey"):
            mock_resp.status_code = 401
        buildinfo = json.load(data)
        if not buildinfo["name"] == "MyBuildName" or not buildinfo["number"] == "42":
            mock_resp.status_code = 400
        mock_resp.content = None
        return mock_resp

    def mock_response_get(url, data=None, **kwargs):
        mock_resp = Mock()
        mock_resp.status_code = 200
        if "conan_sources.tgz" in url:
            mock_resp.status_code = 404
        return mock_resp

    def _test_buildinfo(self, client, user_channel):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, load
            import os
            class Pkg(ConanFile):
                settings = "os"
                {requires}
                exports_sources = "myfile.txt"
                keep_imports = True
                def imports(self):
                    self.copy("myfile.txt", folder=True)
                def package(self):
                    self.copy("*myfile.txt")
                """)
        client.save({"PkgA/conanfile.py": conanfile.format(requires=""),
                     "PkgA/myfile.txt": "HelloA",
                     "PkgB/conanfile.py": conanfile.format(
                         requires='requires = "PkgA/0.1@{}"'.format(user_channel)),
                     "PkgB/myfile.txt": "HelloB",
                     "PkgC/conanfile.py": conanfile.format(
                         requires='requires = "PkgA/0.1@{}"'.format(user_channel)),
                     "PkgC/myfile.txt": "HelloC",
                     "PkgD/conanfile.py": conanfile.format(
                         requires='requires = "PkgC/0.1@{0}", "PkgB/0.1@{0}"'.format(user_channel)),
                     "PkgD/myfile.txt": "HelloD"
                     })
        for profile in ("Windows", "Linux"):
            client.run("create PkgA PkgA/0.1@{} -s os={}".format(user_channel, profile))
            client.run("create PkgB PkgB/0.1@{} -s os={}".format(user_channel, profile))
            client.run("create PkgC PkgC/0.1@{} -s os={}".format(user_channel, profile))
            client.run("create PkgD PkgD/0.1@{} -s os={}".format(user_channel, profile))
            client.run("lock create --reference PkgD/0.1@{} --build=PkgC --build=PkgD -s os={}"
                       " --lockfile-out={}.lock".format(user_channel, profile, profile))

            client.run("create PkgC PkgC/0.1@{0} --lockfile={1}.lock "
                       "--lockfile-out={1}.lock".format(user_channel, profile))
            client.run("create PkgD PkgD/0.1@{0} --lockfile={1}.lock "
                       "--lockfile-out={1}.lock".format(user_channel, profile))
            client.run("upload * --all --confirm -r default")

        sys.argv = ["conan_build_info", "--v2", "start", "MyBuildName", "42"]
        run()
        sys.argv = ["conan_build_info", "--v2", "create",
                    os.path.join(client.current_folder, "buildinfowin.json"), "--lockfile",
                    os.path.join(client.current_folder, "Windows.lock")]
        run()

        sys.argv = ["conan_build_info", "--v2", "create",
                    os.path.join(client.current_folder, "buildinfolinux.json"), "--lockfile",
                    os.path.join(client.current_folder, "Linux.lock")]
        run()

        user_channel = "@" + user_channel if user_channel else user_channel
        buildinfo = json.loads(client.load("buildinfowin.json"))
        self.assertEqual(buildinfo["name"], "MyBuildName")
        self.assertEqual(buildinfo["number"], "42")
        ids_list = [item["id"] for item in buildinfo["modules"]]
        rrev_pkgd, rrev_pkgc, prev_pkgd_win, prev_pkgc_win, prev_pkgd_linux, prev_pkgc_linux = "", "", "", "", "", ""
        if client.cache.config.revisions_enabled:
            rrev_pkgd = "#4923df588db8c6e5867f8df8b8d4e79d" if user_channel else "#a4041e14960e937df21d431579e32e9c"
            rrev_pkgc = "#4fb6c2b0610701ceb5d3b5ccb7a93ecf" if user_channel else "#9d4a7842c95b2ab65b99e2a8834c58da"
            prev_pkgd_win = "#fae36f88c6cc61dafd2afe78687ab248" if user_channel else "#5f50bfa7642cd8924c80b3d6be87b4c5"
            prev_pkgc_win = "#d0f5b7f73cb879dcc78b72ed3af8c85c" if user_channel else "#861f0854c9135d1e753ca9ffe8587d4a"
            prev_pkgd_linux = "#ca5538e3a9abdfcc024ebd96837b7161" if user_channel else "#e6adeb06f3b4296c63a751b5d68ed858"
            prev_pkgc_linux = "#472d19aea10fe10ddf081d13ca716404" if user_channel else "#919776eb660a26575c327cceb2f046f8"

        expected = ["PkgC/0.1{}{}".format(user_channel, rrev_pkgc),
                    "PkgD/0.1{}{}".format(user_channel, rrev_pkgd),
                    "PkgC/0.1{}{}:3374c4fa6b7e865cfc3a1903ae014cf77a6938ec{}".format(user_channel, rrev_pkgc, prev_pkgc_win),
                    "PkgD/0.1{}{}:6cd742f1b907e693abf6da9f767aab3ee7fde606{}".format(user_channel, rrev_pkgd, prev_pkgd_win)]
        self.assertEqual(set(expected), set(ids_list))

        buildinfo = json.loads(client.load("buildinfolinux.json"))
        self.assertEqual(buildinfo["name"], "MyBuildName")
        self.assertEqual(buildinfo["number"], "42")
        ids_list = [item["id"] for item in buildinfo["modules"]]
        expected = ["PkgC/0.1{}{}".format(user_channel, rrev_pkgc),
                    "PkgD/0.1{}{}".format(user_channel, rrev_pkgd),
                    "PkgC/0.1{}{}:a1e39343af463cef4284c5550fde03912afd9852{}".format(user_channel, rrev_pkgc, prev_pkgc_linux),
                    "PkgD/0.1{}{}:39af3f48fdee2bbc5f84e7da3a67ebab2a297acb{}".format(user_channel, rrev_pkgd, prev_pkgd_linux)]
        self.assertEqual(set(expected), set(ids_list))

        sys.argv = ["conan_build_info", "--v2", "update",
                    os.path.join(client.current_folder, "buildinfowin.json"),
                    os.path.join(client.current_folder, "buildinfolinux.json"),
                    "--output-file", os.path.join(client.current_folder, "mergedbuildinfo.json")]
        run()

        f = client.load("mergedbuildinfo.json")
        buildinfo = json.loads(f)
        self.assertEqual(buildinfo["name"], "MyBuildName")
        self.assertEqual(buildinfo["number"], "42")
        ids_list = [item["id"] for item in buildinfo["modules"]]
        expected = ["PkgC/0.1{}{}".format(user_channel, rrev_pkgc),
                    "PkgD/0.1{}{}".format(user_channel, rrev_pkgd),
                    "PkgC/0.1{}{}:3374c4fa6b7e865cfc3a1903ae014cf77a6938ec{}".format(user_channel, rrev_pkgc, prev_pkgc_win),
                    "PkgC/0.1{}{}:a1e39343af463cef4284c5550fde03912afd9852{}".format(user_channel, rrev_pkgc, prev_pkgc_linux),
                    "PkgD/0.1{}{}:6cd742f1b907e693abf6da9f767aab3ee7fde606{}".format(user_channel, rrev_pkgd, prev_pkgd_win),
                    "PkgD/0.1{}{}:39af3f48fdee2bbc5f84e7da3a67ebab2a297acb{}".format(user_channel, rrev_pkgd, prev_pkgd_linux)
                    ]
        self.assertEqual(set(expected), set(ids_list))

        sys.argv = ["conan_build_info", "--v2", "publish",
                    os.path.join(client.current_folder, "mergedbuildinfo.json"), "--url",
                    "http://fakeurl:8081/artifactory", "--user", "user", "--password", "password"]
        run()
        sys.argv = ["conan_build_info", "--v2", "publish",
                    os.path.join(client.current_folder, "mergedbuildinfo.json"), "--url",
                    "http://fakeurl:8081/artifactory", "--apikey", "apikey"]
        run()

        sys.argv = ["conan_build_info", "--v2", "stop"]
        run()

    @patch("conans.build_info.build_info.get_conan_user_home")
    @patch("conans.build_info.build_info.ClientCache")
    @patch("conans.build_info.build_info.requests.put", new=mock_response)
    def test_build_info_create_update_publish(self, mock_cache, user_home_mock):
        base_folder = temp_folder(True)
        cache_folder = os.path.join(base_folder, ".conan")
        servers = {"default": TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                         users={"lasote": "mypass"})}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]},
                            cache_folder=cache_folder)

        mock_cache.return_value = client.cache
        user_home_mock.return_value = base_folder
        user_channels = ["user/channel", ""]
        for user_channel in user_channels:
            self._test_buildinfo(client, user_channel)

    @pytest.mark.tool_git
    @patch("conans.build_info.build_info.get_conan_user_home")
    @patch("conans.build_info.build_info.ClientCache")
    @patch("conans.build_info.build_info.requests.get", new=mock_response_get)
    def test_build_info_create_scm(self, mock_cache, user_home_mock):
        base_folder = temp_folder(True)
        cache_folder = os.path.join(base_folder, ".conan")
        servers = {"default": TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                         users={"lasote": "mypass"})}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]},
                            cache_folder=cache_folder)

        mock_cache.return_value = client.cache
        user_home_mock.return_value = base_folder
        conanfile = textwrap.dedent("""
            from conans import ConanFile, load
            import os
            class Pkg(ConanFile):
                name = "PkgA"
                version = "0.1"
                scm = {"type": "git",
                        "url": "auto",
                        "revision": "auto"}

                def imports(self):
                    self.copy("myfile.txt", folder=True)
                def package(self):
                    self.copy("*myfile.txt")
                """)

        client.save({"conanfile.py": conanfile,
                     "myfile.txt": "HelloA"})
        client.run_command("git init")
        client.run_command('git config user.email "you@example.com"')
        client.run_command('git config user.name "Your Name"')
        client.run_command("git remote add origin https://github.com/fake/fake.git")
        client.run_command("git add .")
        client.run_command("git commit -m \"initial commit\"")

        client.run("export .")

        client.run("lock create conanfile.py --lockfile-out=conan.lock")

        client.run("create . --lockfile=conan.lock")
        client.run("upload * --confirm -r default --force")

        sys.argv = ["conan_build_info", "--v2", "start", "MyBuildName", "42"]
        run()
        sys.argv = ["conan_build_info", "--v2", "create",
                    os.path.join(client.current_folder, "buildinfo.json"), "--lockfile",
                    os.path.join(client.current_folder, LOCKFILE)]
        run()
        if not os.path.exists(os.path.join(client.current_folder, "buildinfo.json")):
            self.fail("build info create failed")

    @patch("conans.build_info.build_info.get_conan_user_home")
    @patch("conans.build_info.build_info.ClientCache")
    def test_build_info_old_lockfile_version(self, mock_cache, user_home_mock):
        base_folder = temp_folder(True)
        cache_folder = os.path.join(base_folder, ".conan")
        client = TestClient(cache_folder=cache_folder)
        client.save({"conan.lock": '{"version": "0.2"}'})
        mock_cache.return_value = client.cache
        user_home_mock.return_value = cache_folder

        sys.argv = ["conan_build_info", "--v2", "start", "MyBuildName", "42"]
        run()
        sys.argv = ["conan_build_info", "--v2", "create",
                    os.path.join(client.current_folder, "buildinfo.json"), "--lockfile",
                    os.path.join(client.current_folder, "conan.lock")]

        old_stderr = sys.stderr
        try:
            result = StringIO()
            sys.stderr = result
            run()
        except SystemExit:
            result = result.getvalue()
            self.assertIn("This lockfile was created with an incompatible version of Conan", result)
        finally:
            sys.stderr = old_stderr
