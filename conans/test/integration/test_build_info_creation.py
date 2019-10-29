import json
import os
import shutil
import sys
import textwrap
import unittest

from mock import patch, Mock

from conans.client.cache.cache import ClientCache
from conans.model.graph_lock import LOCKFILE
from conans.build_info.command import run
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestBufferConanOutput


class MyBuildInfoCreation(unittest.TestCase):
    @patch("conans.build_info.build_info.ClientCache")
    def test_build_info_start(self, mock_cache):
        conan_user_home = temp_folder(True)
        mock_cache.return_value = ClientCache(os.path.join(conan_user_home, ".conan"),
                                              TestBufferConanOutput())
        sys.argv = ["conan_build_info", "--v2", "start", "MyBuildName", "42"]
        run()
        with open(mock_cache.return_value.put_headers_path) as f:
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
        with open(mock_cache.return_value.put_headers_path) as f:
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

    @patch("conans.build_info.build_info.get_conan_user_home")
    @patch("conans.build_info.build_info.ClientCache")
    @patch("conans.build_info.build_info.requests.put", new=mock_response)
    def test_build_info_create_update_publish(self, mock_cache, user_home_mock):
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
        base_folder = temp_folder(True)
        cache_folder = os.path.join(base_folder, ".conan")
        client = TestClient(default_server_user=True, cache_folder=cache_folder)
        mock_cache.return_value = client.cache
        user_home_mock.return_value = base_folder

        client.save({"PkgA/conanfile.py": conanfile.format(requires=""),
                     "PkgA/myfile.txt": "HelloA"})
        client.run("create PkgA PkgA/0.1@user/channel")

        client.save({"PkgB/conanfile.py": conanfile.format(
            requires='requires = "PkgA/0.1@user/channel"'),
            "PkgB/myfile.txt": "HelloB"})
        client.run("create PkgB PkgB/0.1@user/channel")

        client.save({"PkgC/conanfile.py": conanfile.format(
            requires='requires = "PkgA/0.1@user/channel"'),
            "PkgC/myfile.txt": "HelloC"})
        client.run("create PkgC PkgC/0.1@user/channel")

        client.save({"PkgD/conanfile.py": conanfile.format(
            requires='requires = "PkgC/0.1@user/channel", "PkgB/0.1@user/channel"'),
            "PkgD/myfile.txt": "HelloD"})

        client.run("create PkgD PkgD/0.1@user/channel")
        client.run("graph lock PkgD/0.1@user/channel")

        client.run("create PkgA PkgA/0.2@user/channel --lockfile")

        shutil.copy(os.path.join(client.current_folder, "conan.lock"),
                    os.path.join(client.current_folder, "temp.lock"))

        client.run("create PkgB PkgB/0.1@user/channel --lockfile --build missing")

        client.run("upload * --all --confirm")

        sys.argv = ["conan_build_info", "--v2", "start", "MyBuildName", "42"]
        run()
        sys.argv = ["conan_build_info", "--v2", "create",
                    os.path.join(client.current_folder, "buildinfo1.json"), "--lockfile",
                    os.path.join(client.current_folder, LOCKFILE)]
        run()

        shutil.copy(os.path.join(client.current_folder, "temp.lock"),
                    os.path.join(client.current_folder, "conan.lock"))

        client.run("create PkgC PkgC/0.1@user/channel --lockfile --build missing")

        client.run("upload * --all --confirm")

        with open(os.path.join(client.current_folder, "buildinfo1.json")) as f:
            buildinfo = json.load(f)
            self.assertEqual(buildinfo["name"], "MyBuildName")
            self.assertEqual(buildinfo["number"], "42")
            self.assertEqual(buildinfo["modules"][0]["id"], "PkgB/0.1@user/channel")
            self.assertEqual(buildinfo["modules"][0]["artifacts"][0]["name"], "conan_sources.tgz")
            self.assertEqual(buildinfo["modules"][0]["artifacts"][1]["name"], "conanfile.py")
            self.assertEqual(buildinfo["modules"][0]["artifacts"][2]["name"], "conanmanifest.txt")
            self.assertEqual(buildinfo["modules"][0]["dependencies"][0]["id"],
                             "PkgA/0.2@user/channel :: conan_sources.tgz")
            self.assertEqual(buildinfo["modules"][0]["dependencies"][1]["id"],
                             "PkgA/0.2@user/channel :: conanfile.py")
            self.assertEqual(buildinfo["modules"][0]["dependencies"][2]["id"],
                             "PkgA/0.2@user/channel :: conanmanifest.txt")

            self.assertEqual(buildinfo["modules"][1]["id"],
                             "PkgB/0.1@user/channel:09f152eb7b3e0a6e15a2a3f464245864ae8f8644")
            self.assertEqual(buildinfo["modules"][1]["artifacts"][0]["name"], "conan_package.tgz")
            self.assertEqual(buildinfo["modules"][1]["artifacts"][1]["name"], "conan_package.tgz")
            self.assertEqual(buildinfo["modules"][1]["artifacts"][2]["name"], "conan_package.tgz")
            self.assertEqual(buildinfo["modules"][1]["dependencies"][0]["id"],
                             "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conan_package.tgz")
            self.assertEqual(buildinfo["modules"][1]["dependencies"][1]["id"],
                             "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conaninfo.txt")
            self.assertEqual(buildinfo["modules"][1]["dependencies"][2]["id"],
                             "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conanmanifest.txt")

            self.assertEqual(buildinfo["modules"][2]["id"], "PkgA/0.2@user/channel")

        sys.argv = ["conan_build_info", "--v2", "start", "MyBuildName", "42"]
        run()
        sys.argv = ["conan_build_info", "--v2", "create",
                    os.path.join(client.current_folder, "buildinfo2.json"), "--lockfile",
                    os.path.join(client.current_folder, LOCKFILE)]
        run()

        sys.argv = ["conan_build_info", "--v2", "update",
                    os.path.join(client.current_folder, "buildinfo1.json"),
                    os.path.join(client.current_folder, "buildinfo2.json"),
                    "--output-file", os.path.join(client.current_folder, "mergedbuildinfo.json")]
        run()

        with open(os.path.join(client.current_folder, "mergedbuildinfo.json")) as f:
            buildinfo = json.load(f)
            self.assertEqual(buildinfo["name"], "MyBuildName")
            self.assertEqual(buildinfo["number"], "42")
            ids_list = [item["id"] for item in buildinfo["modules"]]
            self.assertTrue("PkgC/0.2@user/channel" in ids_list)
            self.assertTrue("PkgB/0.2@user/channel" in ids_list)

        sys.argv = ["conan_build_info", "--v2", "publish",
                    os.path.join(client.current_folder, "mergedbuildinfo.json"), "--url",
                    "http://fakeurl:8081/artifactory", "--user", "user", "--password", "password"]
        run()
        sys.argv = ["conan_build_info", "--v2", "publish",
                    os.path.join(client.current_folder, "mergedbuildinfo.json"), "--url",
                    "http://fakeurl:8081/artifactory", "--apikey", "apikey"]
        run()
