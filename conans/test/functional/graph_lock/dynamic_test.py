import json
import unittest

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
        lock = client.load("conan.lock")
        print(lock)
        lock = json.loads(lock)["graph_lock"]["nodes"]
        self.assertEqual(4, len(lock))
        libc = lock["1"]
        liba = lock["2"]
        libb = lock["3"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(liba["ref"], "LibA/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(libb["ref"], "LibB/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(libc["ref"], "LibC/0.1#3cc68234fe3b976e1cb15c61afdace6d")
        else:
            self.assertEqual(liba["ref"], "LibA/0.1")
            self.assertEqual(libb["ref"], "LibB/0.1")
            self.assertEqual(libc["ref"], "LibC/0.1")
        self.assertEqual(libc["requires"], ["2", "3"])

        # Remove one dep (LibB) in LibC, will fail to create
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibA/0.1")})
        # If the graph is modified, a create should fail
        client.run("create . LibC/0.1@ --lockfile", assert_error=True)
        self.assertIn("'LibC/0.1' locked requirement 'LibB/0.1' not found", client.out)

        # It is possible to obtain a new lockfile
        client.run("export . LibC/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibC/0.1")})
        client.run("graph lock . --lockfile=new.lock")
        new_lock = client.load("new.lock")
        new_lock_json = json.loads(new_lock)["graph_lock"]["nodes"]
        self.assertEqual(3, len(new_lock_json))
        libc = new_lock_json["1"]
        liba = new_lock_json["2"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(liba["ref"], "LibA/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(libc["ref"], "LibC/0.1#3cc68234fe3b976e1cb15c61afdace6d")
        else:
            self.assertEqual(liba["ref"], "LibA/0.1")
            self.assertEqual(libc["ref"], "LibC/0.1")
        self.assertEqual(libc["requires"], ["2"])

        # It is also possible to use the existing one as base
        client.run("graph lock . --input-lockfile=conan.lock --lockfile=updated.lock")
        updated_lock = client.load("updated.lock")
        self.assertEqual(new_lock, updated_lock)

    def add_dep_test(self):
        # https://github.com/conan-io/conan/issues/5807
        # Modifying dependencies do NOT modify the lockfile
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . zlib/1.0@")

        client.save({"conanfile.py": GenConanfile()})
        client.run("graph lock .")
        client.save({"conanfile.py": GenConanfile().with_require_plain("zlib/1.0")})
        client.run("install . --lockfile", assert_error=True)
        self.assertIn("ERROR: Require 'zlib' cannot be found in lockfile", client.out)
        client.run("install . ")
        self.assertIn("zlib/1.0: Already installed!", client.out)

        # Correct way is generate a new lockfile
        client.run("graph lock .")
        self.assertIn("zlib/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("Generated lockfile", client.out)
        lock_file_json = json.loads(client.load("conan.lock"))
        self.assertNotIn("zlib", lock_file_json)
        self.assertEqual(2, len(lock_file_json["graph_lock"]["nodes"]))
        self.assertEqual("zlib/1.0", lock_file_json["graph_lock"]["nodes"]["1"]["ref"])

    def augment_test_package_requires(self):
        # https://github.com/conan-io/conan/issues/6067
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("tool", "0.1")})
        client.run("create .")

        client.save({"conanfile.py": GenConanfile().with_name("dep").with_version("0.1"),
                     "test_package/conanfile.py": GenConanfile().with_test("pass"),
                     "consumer.txt": "[requires]\ndep/0.1\n",
                     "profile": "[build_requires]\ntool/0.1\n"})

        client.run("export .")
        client.run("graph lock consumer.txt -pr=profile --build missing")
        lock1 = client.load("conan.lock")
        print(lock1)

        # Check lock
        client.run("create . -pr=profile --lockfile --build missing", assert_error=True)
        self.assertIn("The node tool/0.1 ID 5 was not found in the lock", client.out)

        # We need a new lock
        client.run("graph lock test_package -pr=profile --build missing --input-lockfile=conan.lock"
                   " --lockfile=create.lock")
        lock2 = client.load("conan.lock")
        self.assertEqual(lock1, lock2)
        print(client.load("create.lock"))
        client.run("create . -pr=profile --lockfile=create.lock --build missing")

        self.assertIn("tool/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("dep/0.1: Applying build-requirement: tool/0.1", client.out)
        self.assertIn("dep/0.1 (test package): Running test()", client.out)
