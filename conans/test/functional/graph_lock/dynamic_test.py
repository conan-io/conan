import json
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class GraphLockDynamicTest(unittest.TestCase):

    def partial_lock_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        client.save({"conanfile.py": GenConanfile().with_require_plain("LibB/1.0")})
        client.run("create . LibC/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibC/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibC --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libc.lock")

        client.run("create . LibC/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        client.run("create . LibC/1.0@ --lockfile=libc.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)

        # Two levels
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibC/1.0")})
        client.run("create . LibD/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibD/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock")

        client.run("create . LibD/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        client.run("create . LibD/1.0@ --lockfile=libd.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)

    def partial_multiple_matches_lock_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        client.save({"conanfile.py": GenConanfile().with_require_plain("LibB/1.0")
                                                   .with_require_plain("LibA/[>=1.0]")})
        client.run("create . LibC/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibC/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibC --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libc.lock")

        client.run("create . LibC/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        client.run("create . LibC/1.0@ --lockfile=libc.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)

        # Two levels
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibC/1.0")})
        client.run("create . LibD/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibD/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock")

        client.run("create . LibD/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        client.run("create . LibD/1.0@ --lockfile=libd.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)

    def partial_lock_conflict_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        client.save({"conanfile.py": GenConanfile().with_require_plain("LibA/[>=1.0]")})
        client.run("create . LibC/1.0@")

        client.save({"conanfile.py": GenConanfile().with_require_plain("LibB/1.0")
                                                   .with_require_plain("LibC/1.0")})
        client.run("create . LibD/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibD/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)
        self.assertNotIn("LibA/1.0.1", client.out)

        client.run("create . LibD/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        self.assertNotIn("LibA/1.0 from local", client.out)

        client.run("create . LibD/1.0@ --lockfile=libd.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)
        self.assertNotIn("LibA/1.0.1", client.out)

    def partial_lock_root_unused_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        client.save({"conanfile.py": GenConanfile().with_require_plain("LibA/[>=1.0]")})

        client.run("create . LibC/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibC/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibC --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libc.lock", assert_error=True)
        self.assertIn("ERROR: The provided lockfile was not used, there is no overlap.", client.out)

    def remove_dep_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/0.1@")
        client.run("create . LibB/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibA/0.1")
                                                   .with_require_plain("LibB/0.1")})
        client.run("create . LibC/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibC/0.1")})
        client.run("lock create conanfile.py --lockfile-out=conan.lock")
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
        client.run("create . LibC/0.1@ --lockfile=conan.lock", assert_error=True)
        self.assertIn("Attempt to modify locked LibC/0.1", client.out)

        # It is possible to obtain a new lockfile
        client.run("export . LibC/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("LibC/0.1")})
        client.run("lock create conanfile.py --lockfile-out=new.lock")
        # And use the lockfile to build it
        client.run("install LibC/0.1@ --build=LibC --lockfile=new.lock")
        client.run("lock clean-modified new.lock")
        new_lock = client.load("new.lock")
        self.assertNotIn("modified", new_lock)
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

    def add_dep_test(self):
        # https://github.com/conan-io/conan/issues/5807
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . zlib/1.0@")

        client.save({"conanfile.py": GenConanfile()})
        client.run("lock create conanfile.py --lockfile-out=conan.lock")
        client.save({"conanfile.py": GenConanfile().with_require_plain("zlib/1.0")})
        client.run("install . --lockfile=conan.lock", assert_error=True)
        self.assertIn("ERROR: Require 'zlib' cannot be found in lockfile", client.out)

        # Correct way is generate a new lockfile
        client.run("lock create conanfile.py --lockfile-out=new.lock")
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
        client.run("lock create conanfile.py --lockfile=conan.lock --lockfile-out=updated.lock")
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
        client.run("lock create consumer.txt -pr=profile --build=missing --lockfile-out=conan.lock")
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

        client.run("create . --lockfile=conan.lock --lockfile-out=conan.lock "
                   "--build=missing")
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
