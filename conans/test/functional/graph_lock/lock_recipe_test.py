import json
import textwrap
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class LockRecipeTest(unittest.TestCase):

    def lock_recipe_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_setting("os")})
        client.run("create . pkg/0.1@ -s os=Windows")
        self.assertIn("pkg/0.1:3475bd55b91ae904ac96fde0f106a136ab951a5e - Build", client.out)
        self.assertIn("pkg/0.1: Created package revision d0f0357277b3417d3984b5a9a85bbab6",
                      client.out)
        client.run("create . pkg/0.1@ -s os=Linux")
        self.assertIn("pkg/0.1:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31 - Build", client.out)
        self.assertIn("pkg/0.1: Created package revision 9e99cfd92d0d7df79d687b01512ce844",
                      client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1")})
        client.run("lock create conanfile.py --base --lockfile-out=conan.lock")
        lock = json.loads(client.load("conan.lock"))
        self.assertEqual(2, len(lock["graph_lock"]["nodes"]))
        pkg_node = lock["graph_lock"]["nodes"]["1"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(pkg_node["ref"], "pkg/0.1#f096d7d54098b7ad7012f9435d9c33f3")
        else:
            self.assertEqual(pkg_node["ref"], "pkg/0.1")
        client.run("lock create conanfile.py -s os=Linux "
                   "--lockfile-out=linux.lock --lockfile=conan.lock")
        lock = json.loads(client.load("linux.lock"))
        pkg_node = lock["graph_lock"]["nodes"]["1"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(pkg_node["ref"], "pkg/0.1#f096d7d54098b7ad7012f9435d9c33f3")
            self.assertEqual(pkg_node["package_id"], "cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31")
            self.assertEqual(pkg_node["prev"], "9e99cfd92d0d7df79d687b01512ce844")
        else:
            self.assertEqual(pkg_node["ref"], "pkg/0.1")
            self.assertEqual(pkg_node["package_id"], "cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31")
            self.assertEqual(pkg_node["prev"], "0")
        self.assertEqual(pkg_node["options"], "")

        client.run("lock create conanfile.py -s os=Windows "
                   "--lockfile-out=windows.lock --lockfile=conan.lock")
        lock = json.loads(client.load("windows.lock"))
        pkg_node = lock["graph_lock"]["nodes"]["1"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(pkg_node["ref"], "pkg/0.1#f096d7d54098b7ad7012f9435d9c33f3")
            self.assertEqual(pkg_node["package_id"], "3475bd55b91ae904ac96fde0f106a136ab951a5e")
            self.assertEqual(pkg_node["prev"], "d0f0357277b3417d3984b5a9a85bbab6")
        else:
            self.assertEqual(pkg_node["ref"], "pkg/0.1")
            self.assertEqual(pkg_node["package_id"], "3475bd55b91ae904ac96fde0f106a136ab951a5e")
            self.assertEqual(pkg_node["prev"], "0")
        self.assertEqual(pkg_node["options"], "")

    def conditional_lock_recipe_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . common/0.1@")
        client.run("create . win/0.1@")
        client.run("create . linux/0.1@")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "os"
                requires = "common/0.1"
                def requirements(self):
                    if self.settings.os == "Windows":
                        self.requires("win/0.1")
                    else:
                        self.requires("linux/0.1")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("lock create conanfile.py --base -s os=Windows --lockfile-out=conan.lock")
        lock = json.loads(client.load("conan.lock"))
        self.assertEqual(3, len(lock["graph_lock"]["nodes"]))
        common = lock["graph_lock"]["nodes"]["1"]
        win = lock["graph_lock"]["nodes"]["2"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(common["ref"], "common/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(win["ref"], "win/0.1#f3367e0e7d170aa12abccb175fee5f97")
        else:
            self.assertEqual(common["ref"], "common/0.1")
            self.assertEqual(win["ref"], "win/0.1")
        self.assertIsNone(common.get("package_id"))
        self.assertIsNone(common.get("prev"))
        self.assertIsNone(common.get("options"))
        self.assertIsNone(win.get("package_id"))
        self.assertIsNone(win.get("prev"))
        self.assertIsNone(win.get("options"))

        client.run("lock create conanfile.py -s os=Linux "
                   "--lockfile-out=linux.lock --lockfile=conan.lock")
        lock = json.loads(client.load("linux.lock"))
        self.assertEqual(3, len(lock["graph_lock"]["nodes"]))
        common = lock["graph_lock"]["nodes"]["1"]
        linux = lock["graph_lock"]["nodes"]["3"]
        self.assertNotIn("2", lock["graph_lock"]["nodes"])
        if client.cache.config.revisions_enabled:
            self.assertEqual(common["ref"], "common/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(common["prev"], "83c38d3b4e5f1b8450434436eec31b00")
            self.assertEqual(linux["ref"], "linux/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(linux["prev"], "83c38d3b4e5f1b8450434436eec31b00")
        else:
            self.assertEqual(common["ref"], "common/0.1")
            self.assertEqual(common["prev"], "0")
            self.assertEqual(linux["ref"], "linux/0.1")
            self.assertEqual(linux["prev"], "0")
        self.assertEqual(common["options"], "")
        self.assertEqual(common["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(linux["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(linux["options"], "")

        client.run("lock create conanfile.py -s os=Windows "
                   "--lockfile-out=windows.lock --lockfile=conan.lock")
        lock = json.loads(client.load("windows.lock"))
        self.assertEqual(3, len(lock["graph_lock"]["nodes"]))
        common = lock["graph_lock"]["nodes"]["1"]
        win = lock["graph_lock"]["nodes"]["2"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(common["ref"], "common/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(common["prev"], "83c38d3b4e5f1b8450434436eec31b00")
            self.assertEqual(win["ref"], "win/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(win["prev"], "83c38d3b4e5f1b8450434436eec31b00")
        else:
            self.assertEqual(common["ref"], "common/0.1")
            self.assertEqual(common["prev"], "0")
            self.assertEqual(win["ref"], "win/0.1")
            self.assertEqual(win["prev"], "0")
        self.assertEqual(common["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(common["options"], "")
        self.assertEqual(win["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(win["options"], "")
