import unittest

from conans.model.graph_lock import GraphLockFile
from conans.test.utils.tools import TestClient, GenConanfile


class GraphLockDynamicTest(unittest.TestCase):

    def remove_dep_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/0.1@")
        client.run("create . LibB/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibA/0.1")
                                                   .with_require_plain("LibB/0.1")})
        client.run("create . LibC/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibC/0.1")})
        client.run("graph lock .")
        lock = GraphLockFile.load(client.current_folder, False)
        self.assertEqual(4, len(lock.graph_lock._nodes))
        # Remove one dep in LibC
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibA/0.1")})
        client.run("create . LibC/0.1@ --lockfile")
        lock = GraphLockFile.load(client.current_folder, False)
        print (lock.graph_lock._nodes)
        self.assertEqual(3, len(lock.graph_lock._nodes))



