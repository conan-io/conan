import json
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
        client.run("graph lock . --recipes")
        print(client.load("conan.lock"))
        lock = json.loads(client.load("conan.lock"))
        pkg_node = lock["graph_lock"]["nodes"]["1"]
        self.assertEqual(pkg_node["ref"], "pkg/0.1#f096d7d54098b7ad7012f9435d9c33f3")
        self.assertIsNone(pkg_node.get("package_id"))
        self.assertIsNone(pkg_node.get("prev"))
        self.assertIsNone(pkg_node.get("options"))

        client.run("graph lock . -s os=Linux --lockfile=linux.lock --input-lockfile=conan.lock")
        lock = json.loads(client.load("linux.lock"))
        pkg_node = lock["graph_lock"]["nodes"]["1"]
        self.assertEqual(pkg_node["ref"], "pkg/0.1#f096d7d54098b7ad7012f9435d9c33f3")
        self.assertEqual(pkg_node["package_id"], "cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31")
        self.assertEqual(pkg_node["prev"], "9e99cfd92d0d7df79d687b01512ce844")
        self.assertEqual(pkg_node["options"], "")

        client.run("graph lock . -s os=Windows --lockfile=windows.lock --input-lockfile=conan.lock")
        lock = json.loads(client.load("windows.lock"))
        pkg_node = lock["graph_lock"]["nodes"]["1"]
        self.assertEqual(pkg_node["ref"], "pkg/0.1#f096d7d54098b7ad7012f9435d9c33f3")
        self.assertEqual(pkg_node["package_id"], "3475bd55b91ae904ac96fde0f106a136ab951a5e")
        self.assertEqual(pkg_node["prev"], "d0f0357277b3417d3984b5a9a85bbab6")
        self.assertEqual(pkg_node["options"], "")


class BasicLockTest(unittest.TestCase):

    def lock_build_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . pkg/0.1@")

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1")})
        client.run("graph lock . --build")
        lock = json.loads(client.load("conan.lock"))
        pkg_node = lock["graph_lock"]["nodes"]["1"]
        self.assertEqual(pkg_node["ref"], "pkg/0.1#f3367e0e7d170aa12abccb175fee5f97")
        self.assertEqual(pkg_node["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertIsNone(pkg_node.get("prev"))
        self.assertEqual(pkg_node["options"], "")
        self.assertIn("pkg/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
