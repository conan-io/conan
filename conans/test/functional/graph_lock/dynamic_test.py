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
        if client.cache.config.revisions_enabled:
            self.assertIn("Attempt to modify locked LibC/0.1", client.out)
        else:
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
            self.assertEqual(libc["ref"], "LibC/0.1#ec5e114a9ad4f4269bc4a221b26eb47a")
        else:
            self.assertEqual(liba["ref"], "LibA/0.1")
            self.assertEqual(libc["ref"], "LibC/0.1")
        self.assertEqual(libc["requires"], ["2"])

        # It is also possible to use the existing one as base
        if not client.cache.config.revisions_enabled:
            # This only works if revisions disabled, otherwise, the revision is locked
            client.run("graph lock . --input-lockfile=conan.lock --lockfile=updated.lock")
            updated_lock = client.load("updated.lock")
            self.assertEqual(new_lock, updated_lock)

    def add_dep_test(self):
        # https://github.com/conan-io/conan/issues/5807
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . zlib/1.0@")

        client.save({"conanfile.py": GenConanfile()})
        client.run("graph lock .")
        client.save({"conanfile.py": GenConanfile().with_require_plain("zlib/1.0")})
        client.run("install . --lockfile", assert_error=True)
        self.assertIn("ERROR: Require 'zlib' cannot be found in lockfile", client.out)

        # Correct way is generate a new lockfile
        client.run("graph lock . --lockfile=new.lock")
        self.assertIn("zlib/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("Generated lockfile", client.out)
        new = client.load("new.lock")
        lock_file_json = json.loads(new)
        self.assertEqual(2, len(lock_file_json["graph_lock"]["nodes"]))
        zlib = lock_file_json["graph_lock"]["nodes"]["1"]["ref"]
        if client.cache.config.revisions_enabled:
            self.assertEqual("zlib/1.0#f3367e0e7d170aa12abccb175fee5f97", zlib)
        else:
            self.assertEqual("zlib/1.0", zlib)

        # augment the existing one, works only because it is a consumer only, not package
        client.run("graph lock . --input-lockfile=conan.lock --lockfile=updated.lock")
        updated = client.load("updated.lock")
        self.assertEqual(updated, new)

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
        json_lock1 = json.loads(lock1)
        dep = json_lock1["graph_lock"]["nodes"]["1"]
        self.assertEqual(dep["build_requires"], ["2"])
        self.assertEqual(dep["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        if client.cache.config.revisions_enabled:
            self.assertEqual(dep["ref"], "dep/0.1#01b22a14739e1e2d4cd409c45cac6422")
            self.assertEqual(dep.get("prev"), None)
        else:
            self.assertEqual(dep["ref"], "dep/0.1")
            self.assertEqual(dep.get("prev"), None)

        client.run("create . -pr=profile --lockfile --build missing")
        self.assertIn("dep/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        self.assertIn("tool/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        lock2 = client.load("conan.lock")
        json_lock2 = json.loads(lock2)
        dep = json_lock2["graph_lock"]["nodes"]["1"]
        self.assertEqual(dep["build_requires"], ["2"])
        self.assertEqual(dep["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        if client.cache.config.revisions_enabled:
            self.assertEqual(dep["ref"], "dep/0.1#01b22a14739e1e2d4cd409c45cac6422")
            self.assertEqual(dep["prev"], "08cd3e7664b886564720123959c05bdf")
        else:
            self.assertEqual(dep["ref"], "dep/0.1")
            self.assertEqual(dep["prev"], "0")
