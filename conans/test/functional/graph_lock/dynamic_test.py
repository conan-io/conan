import json
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class GraphLockDynamicTest(unittest.TestCase):

    def remove_dep_test(self):
        # Removing a dependency do not modify the graph of the lockfile
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/0.1@")
        client.run("create . LibB/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibA/0.1")
                                                   .with_require_plain("LibB/0.1")})
        client.run("create . LibC/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibC/0.1")})
        client.run("graph lock .")
        lock1 = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        self.assertEqual(4, len(lock1))
        self.assertIn("LibC", lock1["1"]["pref"])
        self.assertEqual(lock1["1"]["requires"], ["2", "3"])
        # Remove one dep in LibC
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibA/0.1")})
        client.run("create . LibC/0.1@ --lockfile")
        lock2 = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        self.assertEqual(4, len(lock2))
        self.assertIn("LibC", lock2["1"]["pref"])
        self.assertEqual(lock2["1"]["requires"], ["2", "3"])
