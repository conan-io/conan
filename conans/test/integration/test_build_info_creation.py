import json
import os
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
        sys.argv = ["conan_build_info", "start", "MyBuildName", "42"]
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
        sys.argv = ["conan_build_info", "stop"]
        run()
        with open(mock_cache.return_value.put_headers_path) as f:
            content = f.read()
            self.assertEqual("", content)

    def mock_response(url, data=None, **kwargs):
        mock_resp = Mock()
        mock_resp.status_code = 204
        if "api/build" in url:
            mock_resp.status_code = 204
        if kwargs.get("auth", None) and (kwargs["auth"][0] != "user" or kwargs["auth"][1] != "password"):
            mock_resp.status_code = 401
        elif kwargs["headers"].get("X-JFrog-Art-Api", None) and kwargs["headers"]["X-JFrog-Art-Api"] != "apikey":
            mock_resp.status_code = 401
        buildinfo = json.load(data)
        if not buildinfo["name"] == "MyBuildInfo" or not buildinfo["number"] == "42":
            mock_resp.status_code = 400
        mock_resp.content = None
        return mock_resp

    @patch("conans.build_info.build_info.ClientCache")
    @patch("conans.build_info.build_info.requests.put', new=mock_response)
    def test_build_info_create_update_publish(self, mock_cache):
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
        client = TestClient(default_server_user=True)
        mock_cache.return_value = client.cache
        client.save({"conanfile.py": conanfile.format(requires=""),
                     "myfile.txt": "HelloA"})
        client.run("create . PkgA/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgA/0.1@user/channel"'),
            "myfile.txt": "HelloB"})
        client.run("create . PkgB/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgB/0.1@user/channel"'),
            "myfile.txt": "HelloC"})
        client.run("create . PkgC/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgC/0.1@user/channel"'),
            "myfile.txt": "HelloD"})
        client.run("create . PkgD/0.1@user/channel")
        client.run("graph lock PkgD/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgA/0.1@user/channel"'),
            "myfile.txt": "HelloB"})
        client.run("create . PkgB/0.2@user/channel --lockfile")

        client.run("upload * --all --confirm")
        sys.argv = ["conan_build_info", "start", "MyBuildName", "42"]
        run()
        sys.argv = ["conan_build_info", "create",
                    os.path.join(client.current_folder, "buildinfo.json"), "--lockfile",
                    os.path.join(client.current_folder, LOCKFILE)]
        run()

        with open(os.path.join(client.current_folder, "buildinfo.json")) as f:
            buildinfo = json.load(f)
            self.assertEqual(buildinfo["name"], "MyBuildName")
            self.assertEqual(buildinfo["number"], "42")
            self.assertEqual(buildinfo["modules"][0]["id"], "PkgB/0.2@user/channel")
            self.assertEqual(buildinfo["modules"][1]["id"],
                             "PkgB/0.2@user/channel:5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5")
            self.assertEqual(buildinfo["modules"][0]["artifacts"][0]["name"], "conan_sources.tgz")
            self.assertEqual(buildinfo["modules"][1]["artifacts"][0]["name"], "conan_package.tgz")

        # now test update build_info
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgB/0.2@user/channel"'),
            "myfile.txt": "HelloC"})
        client.run("create . PkgC/0.2@user/channel --lockfile")
        client.run("upload * --all --confirm")
        sys.argv = ["conan_build_info", "create",
                    os.path.join(client.current_folder, "buildinfo_b.json"), "--lockfile",
                    os.path.join(client.current_folder, LOCKFILE),
                    "--user", "user", "--password", "password"]
        run()

        sys.argv = ["conan_build_info", "update",
                    os.path.join(client.current_folder, "buildinfo.json"),
                    os.path.join(client.current_folder, "buildinfo_b.json"),
                    "--output-file", os.path.join(client.current_folder, "mergedbuildinfo.json")]
        run()

        with open(os.path.join(client.current_folder, "mergedbuildinfo.json")) as f:
            buildinfo = json.load(f)
            self.assertEqual(buildinfo["name"], "MyBuildName")
            self.assertEqual(buildinfo["number"], "42")
            ids_list = [item["id"] for item in buildinfo["modules"]]
            self.assertTrue("PkgC/0.2@user/channel" in ids_list)
            self.assertTrue("PkgB/0.2@user/channel" in ids_list)

        sys.argv = ["conan_build_info", "publish",
                    os.path.join(client.current_folder, "mergedbuildinfo.json"), "--url",
                    "http://fakeurl:8081/artifactory", "--user", "user", "--password", "password"]
        run()
        sys.argv = ["conan_build_info", "publish",
                    os.path.join(client.current_folder, "mergedbuildinfo.json"), "--url",
                    "http://fakeurl:8081/artifactory", "--apikey", "apikey"]
        run()
