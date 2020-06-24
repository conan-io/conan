import json
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class GraphLockBuildRequireTestCase(unittest.TestCase):

    def test_duplicated_build_require(self):
        t = TestClient()
        t.save({
            'br/conanfile.py': GenConanfile("br", "0.1"),
            'zlib/conanfile.py': GenConanfile("zlib", "0.1").with_build_require_plain("br/0.1"),
            'bzip2/conanfile.py': GenConanfile("bzip2", "0.1").with_build_require_plain("br/0.1"),
            'boost/conanfile.py': GenConanfile("boost", "0.1").with_require_plain("zlib/0.1")
                                                              .with_require_plain("bzip2/0.1")
                                                              .with_build_require_plain("br/0.1")
            })
        t.run("export br/conanfile.py")
        t.run("export zlib/conanfile.py")
        t.run("export bzip2/conanfile.py")

        # Create lock
        t.run("graph lock boost/conanfile.py --build")
        lock_json = json.loads(t.load("conan.lock"))
        br = lock_json["graph_lock"]["nodes"]["3"]
        self.assertIn("br/0.1", br["ref"])
        self.assertIsNone(br.get("prev"))

        # Compute build order
        t.run("graph build-order conan.lock --json=bo.json")
        if t.cache.config.revisions_enabled:
            expected = [[['3', 'br/0.1@#99b906c1d69c56560d0b12ff2b3d10c0']],
                        [['1', 'zlib/0.1@#1ce889ac4d50e301d4817064b4e4b6ee'],
                         ['2', 'bzip2/0.1@#ac5d76c1046b5effa212f7f69c409a0c']]]
        else:
            expected = [[['3', 'br/0.1@']], [['1', 'zlib/0.1@'], ['2', 'bzip2/0.1@']]]
        self.assertEqual(expected, json.loads(t.load("bo.json")))

        # Create the first element of build order
        t.run("install br/0.1@ --lockfile=conan.lock --build=br/0.1")
        self.assertIn("br/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", t.out)
        self.assertIn("br/0.1: Created package revision", t.out)

    def test_package_both_contexts(self):
        t = TestClient()
        t.save({
            'protobuf/conanfile.py': GenConanfile("protobuf", "0.1"),
            'lib/conanfile.py': GenConanfile("lib", "0.1").with_require_plain("protobuf/0.1")
                                                          .with_build_require_plain("protobuf/0.1"),
            'app/conanfile.py': GenConanfile("app", "0.1").with_require_plain("lib/0.1")
        })
        t.run("export protobuf/conanfile.py")
        t.run("export lib/conanfile.py")
        t.run("export app/conanfile.py")

        # Create lock
        t.run("graph lock app/conanfile.py --profile:build=default --profile:host=default --build")
        lock_json = json.loads(t.load("conan.lock"))
        br = lock_json["graph_lock"]["nodes"]["3"]
        self.assertIn("protobuf/0.1", br["ref"])
        self.assertIsNone(br.get("prev"))

        # Compute build order
        t.run("graph build-order conan.lock --json=bo.json")
        if t.cache.config.revisions_enabled:
            expected = [[['2', 'protobuf/0.1@#a2f7b9ca9a4d2ebe512f9bc455802d34']],
                        [['1', 'lib/0.1@#fe41709ab1369302057c10371e86213c']]]
        else:
            expected = [[['2', 'protobuf/0.1@']], [['1', 'lib/0.1@']]]
        self.assertEqual(expected, json.loads(t.load("bo.json")))

        # Create the first element of build order
        t.run("install protobuf/0.1@ --profile:build=default --profile:host=default "
              "--lockfile=conan.lock --build=protobuf")
        self.assertIn("protobuf/0.1: Created package revision", t.out)
