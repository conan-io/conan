import json
import os
import shutil
import sys
import textwrap
import unittest

from mock import patch, Mock
from six import StringIO

from conans.client.cache.cache import ClientCache
from conans.model.graph_lock import LOCKFILE
from conans.build_info.command import run
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestBufferConanOutput, TestServer


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
        elif kwargs["headers"].get("X-JFrog-Art-Api", None) and kwargs["headers"][
            "X-JFrog-Art-Api"] != "apikey":
            mock_resp.status_code = 401
        buildinfo = json.load(data)
        if not buildinfo["name"] == "MyBuildInfo" or not buildinfo["number"] == "42":
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
                {requires}
                exports_sources = "myfile.txt"
                keep_imports = True
                def imports(self):
                    self.copy("myfile.txt", folder=True)
                def package(self):
                    self.copy("*myfile.txt")
                """)
        client.save({"PkgA/conanfile.py": conanfile.format(requires=""),
                     "PkgA/myfile.txt": "HelloA"})
        client.run("create PkgA PkgA/0.1@{}".format(user_channel))

        client.save({"PkgB/conanfile.py": conanfile.format(
            requires='requires = "PkgA/0.1@{}"'.format(user_channel)),
            "PkgB/myfile.txt": "HelloB"})
        client.run("create PkgB PkgB/0.1@{}".format(user_channel))

        client.save({"PkgC/conanfile.py": conanfile.format(
            requires='requires = "PkgA/0.1@{}"'.format(user_channel)),
            "PkgC/myfile.txt": "HelloC"})
        client.run("create PkgC PkgC/0.1@{}".format(user_channel))

        client.save({"PkgD/conanfile.py": conanfile.format(
            requires='requires = "PkgC/0.1@{0}", "PkgB/0.1@{0}"'.format(user_channel)),
            "PkgD/myfile.txt": "HelloD"})

        client.run("create PkgD PkgD/0.1@{}".format(user_channel))
        client.run("graph lock PkgD/0.1@{}".format(user_channel))

        client.run("create PkgA PkgA/0.2@{} --lockfile".format(user_channel))

        shutil.copy(os.path.join(client.current_folder, "conan.lock"),
                    os.path.join(client.current_folder, "temp.lock"))

        client.run("create PkgB PkgB/0.1@{} --lockfile --build missing".format(user_channel))
        client.run("upload * --all --confirm -r default")

        sys.argv = ["conan_build_info", "--v2", "start", "MyBuildName", "42"]
        run()
        sys.argv = ["conan_build_info", "--v2", "create",
                    os.path.join(client.current_folder, "buildinfo1.json"), "--lockfile",
                    os.path.join(client.current_folder, LOCKFILE)]
        run()

        shutil.copy(os.path.join(client.current_folder, "temp.lock"),
                    os.path.join(client.current_folder, "conan.lock"))

        client.run("create PkgC PkgC/0.1@{} --lockfile --build missing".format(user_channel))
        client.run("upload * --all --confirm -r default")

        sys.argv = ["conan_build_info", "--v2", "create",
                    os.path.join(client.current_folder, "buildinfo2.json"), "--lockfile",
                    os.path.join(client.current_folder, LOCKFILE)]
        run()

        user_channel = "@" + user_channel if len(user_channel) > 2 else user_channel
        f = client.load("buildinfo1.json")
        buildinfo = json.loads(f)
        self.assertEqual(buildinfo["name"], "MyBuildName")
        self.assertEqual(buildinfo["number"], "42")
        ids_list = [item["id"] for item in buildinfo["modules"]]
        self.assertTrue("PkgB/0.1{}".format(user_channel) in ids_list)
        self.assertTrue("PkgB/0.1{}:09f152eb7b3e0a6e15a2a3f464245864ae8f8644".format(
            user_channel) in ids_list)

        sys.argv = ["conan_build_info", "--v2", "update",
                    os.path.join(client.current_folder, "buildinfo1.json"),
                    os.path.join(client.current_folder, "buildinfo2.json"),
                    "--output-file", os.path.join(client.current_folder, "mergedbuildinfo.json")]
        run()

        f = client.load("mergedbuildinfo.json")
        buildinfo = json.loads(f)
        self.assertEqual(buildinfo["name"], "MyBuildName")
        self.assertEqual(buildinfo["number"], "42")
        ids_list = [item["id"] for item in buildinfo["modules"]]
        self.assertTrue("PkgC/0.1{}".format(user_channel) in ids_list)
        self.assertTrue("PkgB/0.1{}".format(user_channel) in ids_list)
        self.assertTrue("PkgC/0.1{}:09f152eb7b3e0a6e15a2a3f464245864ae8f8644".format(
            user_channel) in ids_list)
        self.assertTrue("PkgB/0.1{}:09f152eb7b3e0a6e15a2a3f464245864ae8f8644".format(
            user_channel) in ids_list)

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
        user_channels = ["", "user/channel"]
        for user_channel in user_channels:
            self._test_buildinfo(client, user_channel)

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

        client.run("graph lock .")

        client.run("create . --lockfile")
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
            result = result.getvalue()
            self.assertIn("This lockfile was created with a previous incompatible version", result)
        finally:
            sys.stderr = old_stderr
