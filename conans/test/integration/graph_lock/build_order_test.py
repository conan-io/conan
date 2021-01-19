import json
import unittest

import pytest
from parameterized import parameterized

from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.env_reader import get_env


class BuildOrderTest(unittest.TestCase):

    def test_single_consumer(self):
        # https://github.com/conan-io/conan/issues/5727
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("test4", "0.1")})
        client.run("lock create conanfile.py --build --lockfile-out=conan.lock")
        client.run("lock build-order conan.lock --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual([], jsonbo)

    def test_base_graph(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("test4", "0.1")})
        client.run("lock create conanfile.py --base --lockfile-out=conan.lock")
        client.run("lock build-order conan.lock --json=bo.json", assert_error=True)
        self.assertIn("Lockfiles with --base do not contain profile information, "
                      "cannot be used. Create a full lockfile", client.out)

    @parameterized.expand([(True,), (False,)])
    def test_build_not_locked(self, export):
        # https://github.com/conan-io/conan/issues/5727
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("test4", "0.1")})
        if export:
            client.run("export .")
            client.run("lock create --reference=test4/0.1@ --lockfile-out=conan.lock")
        else:
            client.run("create .")
            client.run("lock create --reference=test4/0.1@ --build=test4 --lockfile-out=conan.lock")
        if client.cache.config.revisions_enabled:
            ref = "test4/0.1#f876ec9ea0f44cb7adb1588e431b391a"
            prev = "92cf292e73488c3527dab5f5ba81b947"
            build_order = [[["test4/0.1@#f876ec9ea0f44cb7adb1588e431b391a",
                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", "host", "1"]]]
        else:
            ref = "test4/0.1"
            prev = "0"
            build_order = [[["test4/0.1@", "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", "host", "1"]]]
        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        test4 = locked["1"]
        self.assertEqual(test4["ref"], ref)
        self.assertEqual(test4["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(test4.get("prev"), None)  # PREV is not defined yet, only exported
        client.run("lock build-order conan.lock --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual(build_order, jsonbo)
        client.run("install test4/0.1@ --lockfile=conan.lock --lockfile-out=conan.lock --build")
        self.assertIn("test4/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        test4 = locked["1"]
        self.assertEqual(test4["ref"], ref)
        self.assertEqual(test4["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(test4["prev"], prev)

        # New build order, nothing else to do
        client.run("lock build-order conan.lock --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual([], jsonbo)

    def test_build_locked_error(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("test4", "0.1")})
        client.run("create .")
        client.run("lock create --reference=test4/0.1@ --lockfile-out=conan.lock")
        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        test4 = locked["1"]
        if client.cache.config.revisions_enabled:
            ref = "test4/0.1#f876ec9ea0f44cb7adb1588e431b391a"
            prev = "92cf292e73488c3527dab5f5ba81b947"
        else:
            ref = "test4/0.1"
            prev = "0"
        self.assertEqual(test4["ref"], ref)
        self.assertEqual(test4["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(test4["prev"], prev)
        client.run("lock build-order conan.lock --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual([], jsonbo)
        # if we try to build anyway, error
        client.run("install test4/0.1@ --lockfile=conan.lock --build", assert_error=True)
        rev = "#f876ec9ea0f44cb7adb1588e431b391a" if client.cache.config.revisions_enabled else ""
        self.assertIn("Cannot build 'test4/0.1{}' because it is "
                      "already locked in the input lockfile".format(rev), client.out)

    @parameterized.expand([(True,), (False,)])
    def test_transitive_build_not_locked(self, export):
        # https://github.com/conan-io/conan/issues/5727
        client = TestClient()
        client.save({"dep/conanfile.py": GenConanfile(),
                     "pkg/conanfile.py": GenConanfile().with_require("dep/0.1"),
                     "app/conanfile.py": GenConanfile().with_require("pkg/0.1")})
        if export:
            client.run("export dep dep/0.1@")
            client.run("export pkg pkg/0.1@")
            client.run("export app app/0.1@")
            client.run("lock create --reference=app/0.1@ --lockfile-out=conan.lock")
        else:
            client.run("create dep dep/0.1@")
            client.run("create pkg pkg/0.1@")
            client.run("create app app/0.1@")
            client.run("lock create --reference=app/0.1@ --build --lockfile-out=conan.lock")

        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]

        if client.cache.config.revisions_enabled:
            build_order = [[["dep/0.1@#f3367e0e7d170aa12abccb175fee5f97",
                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", "host", "3"]],
                           [["pkg/0.1@#447b56f0334b7e2a28aa86e218c8b3bd",
                             "0b3845ce7fd8c0b4e46566097797bd872cb5bcf6", "host", "2"]],
                           [["app/0.1@#5e0af887c3e9391c872773734ccd2ca0",
                             "745ccd40fd696b66b0cb160fd5251a533563bbb4", "host", "1"]]]
            prev_dep = "83c38d3b4e5f1b8450434436eec31b00"
            prev_pkg = "bcde0c25612a6d296cf2cab2c264054d"
            prev_app = "9f30558ce471f676e3e06b633aabcf99"
        else:
            build_order = [[["dep/0.1@",
                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", "host", "3"]],
                           [["pkg/0.1@",
                             "0b3845ce7fd8c0b4e46566097797bd872cb5bcf6", "host", "2"]],
                           [["app/0.1@",
                             "745ccd40fd696b66b0cb160fd5251a533563bbb4", "host", "1"]]]
            prev_dep = "0"
            prev_pkg = "0"
            prev_app = "0"

        for level in build_order:
            for item in level:
                ref, package_id, _, lockid = item
                ref = ref.replace("@", "")
                node = locked[lockid]
                self.assertEqual(node["ref"], ref)
                self.assertEqual(node["package_id"], package_id)
                self.assertEqual(node.get("prev"), None)  # PREV is not defined yet, only exported

        client.run("lock build-order conan.lock --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual(build_order, jsonbo)

        if export:
            client.run("install app/0.1@ --lockfile=conan.lock", assert_error=True)
            self.assertIn("Missing prebuilt package for 'app/0.1', 'dep/0.1', 'pkg/0.1'", client.out)

        # Build one by one
        client.run("install {0} --lockfile=conan.lock --lockfile-out=conan.lock"
                   " --build={0}".format(build_order[0][0][0]))
        self.assertIn("dep/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        node = locked["3"]
        self.assertEqual(node.get("prev"), prev_dep)
        node = locked["2"]
        self.assertEqual(node.get("prev"), None)  # PREV is not defined yet, only exported
        node = locked["1"]
        self.assertEqual(node.get("prev"), None)  # PREV is not defined yet, only exported

        client.run("lock build-order conan.lock --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual(build_order[1:], jsonbo)

        client.run("install pkg/0.1@ --lockfile=conan.lock --build", assert_error=True)
        rev = "#f3367e0e7d170aa12abccb175fee5f97" if client.cache.config.revisions_enabled else ""
        self.assertIn("Cannot build 'dep/0.1{}' because it is "
                      "already locked in the input lockfile".format(rev), client.out)
        client.run("install {0} --lockfile=conan.lock --lockfile-out=conan.lock "
                   "--build={0}".format(build_order[1][0][0]))
        self.assertIn("dep/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("pkg/0.1:0b3845ce7fd8c0b4e46566097797bd872cb5bcf6 - Build", client.out)
        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        node = locked["3"]
        self.assertEqual(node.get("prev"), prev_dep)
        node = locked["2"]
        self.assertEqual(node.get("prev"), prev_pkg)
        node = locked["1"]
        self.assertEqual(node.get("prev"), None)  # PREV is not defined yet, only exported

        client.run("lock build-order conan.lock --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual(build_order[2:], jsonbo)

        client.run("install app/0.1@ --lockfile=conan.lock --build", assert_error=True)
        rev = "#f3367e0e7d170aa12abccb175fee5f97" if client.cache.config.revisions_enabled else ""
        self.assertIn("Cannot build 'dep/0.1{}' because it is "
                      "already locked in the input lockfile".format(rev), client.out)
        client.run("install {0} --lockfile=conan.lock --lockfile-out=conan.lock "
                   "--build={0}".format(build_order[2][0][0]))
        self.assertIn("dep/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("pkg/0.1:0b3845ce7fd8c0b4e46566097797bd872cb5bcf6 - Cache", client.out)
        self.assertIn("app/0.1:745ccd40fd696b66b0cb160fd5251a533563bbb4 - Build", client.out)

        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        node = locked["3"]
        self.assertEqual(node.get("prev"), prev_dep)
        node = locked["2"]
        self.assertEqual(node.get("prev"), prev_pkg)
        node = locked["1"]
        self.assertEqual(node.get("prev"), prev_app)

        # New build order, nothing else to do
        client.run("lock build-order conan.lock --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual([], jsonbo)

    @pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
    def test_package_revision_mode_build_order(self):
        # https://github.com/conan-io/conan/issues/6232
        client = TestClient()
        client.run("config set general.default_package_id_mode=package_revision_mode")
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . libb/0.1@")
        client.run("export . libc/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require("libc/0.1")})
        client.run("export . liba/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require("liba/0.1")
                                                   .with_require("libb/0.1")})
        client.run("export . app/0.1@")

        client.run("lock create --reference=app/0.1@ --build=missing --lockfile-out=conan.lock")
        self.assertIn("app/0.1:Package_ID_unknown - Unknown", client.out)
        self.assertIn("liba/0.1:Package_ID_unknown - Unknown", client.out)
        self.assertIn("libb/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        self.assertIn("libc/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        lock = json.loads(client.load("conan.lock"))
        app = lock["graph_lock"]["nodes"]["1"]
        self.assertEqual(app["package_id"], "Package_ID_unknown")
        liba = lock["graph_lock"]["nodes"]["2"]
        self.assertEqual(liba["package_id"], "Package_ID_unknown")
        libc = lock["graph_lock"]["nodes"]["3"]
        self.assertEqual(libc["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        libd = lock["graph_lock"]["nodes"]["4"]
        self.assertEqual(libd["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

        client.run("lock build-order conan.lock --json=bo.json")
        bo = client.load("bo.json")
        build_order = json.loads(bo)
        expected = [[['libc/0.1@#f3367e0e7d170aa12abccb175fee5f97',
                      '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '3'],
                     ['libb/0.1@#f3367e0e7d170aa12abccb175fee5f97',
                      '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '4']],
                    [['liba/0.1@#7086607aa6efbad8e2527748e3ee8237',
                      'Package_ID_unknown', 'host', '2']],
                    [['app/0.1@#7742ee9e2f19af4f9ed7619f231ca871',
                      'Package_ID_unknown', 'host', '1']]]
        self.assertEqual(build_order, expected)


class BuildRequiresBuildOrderTest(unittest.TestCase):

    @parameterized.expand([(True,), (False,)])
    def test_transitive_build_not_locked(self, export):
        # https://github.com/conan-io/conan/issues/5727
        client = TestClient()
        client.save({"dep/conanfile.py": GenConanfile(),
                     "pkg/conanfile.py": GenConanfile().with_build_requires("dep/0.1"),
                     "app/conanfile.py": GenConanfile().with_require("pkg/0.1")})
        if export:
            client.run("export dep dep/0.1@")
            client.run("export pkg pkg/0.1@")
            client.run("export app app/0.1@")
            # Necessary for build-requires
            client.run("lock create --reference app/0.1@ --build=missing --lockfile-out=conan.lock")
        else:
            client.run("create dep dep/0.1@")
            client.run("create pkg pkg/0.1@")
            client.run("create app app/0.1@")
            client.run("lock create --reference=app/0.1@ --build --lockfile-out=conan.lock")

        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]

        if client.cache.config.revisions_enabled:
            build_order = [[["dep/0.1@#f3367e0e7d170aa12abccb175fee5f97",
                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", "host", "3"]],
                           [["pkg/0.1@#1364f701b47130c7e38f04c5e5fab985",
                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", "host", "2"]],
                           [["app/0.1@#5e0af887c3e9391c872773734ccd2ca0",
                             "a925a8281740e4cb4bcad9cf41ecc4c215210604", "host", "1"]]]
            prev_dep = "83c38d3b4e5f1b8450434436eec31b00"
            prev_pkg = "5d3d587702b55a456c9b6b71e5f40cfa"
            prev_app = "eeb6de9b69fb0905e15788315f77a8e2"

        else:
            build_order = [[["dep/0.1@",
                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", "host", "3"]],
                           [["pkg/0.1@",
                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", "host", "2"]],
                           [["app/0.1@",
                             "a925a8281740e4cb4bcad9cf41ecc4c215210604", "host", "1"]]]
            prev_dep = "0"
            prev_pkg = "0"
            prev_app = "0"

        for level in build_order:
            for item in level:
                ref, package_id, _, lockid = item
                ref = ref.replace("@", "")
                node = locked[lockid]
                self.assertEqual(node["ref"], ref)
                self.assertEqual(node["package_id"], package_id)
                self.assertEqual(node.get("prev"), None)  # PREV is not defined yet, only exported

        client.run("lock build-order conan.lock --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual(build_order, jsonbo)

        # prev is None, --build needs to be explicit or it will fail
        if export:
            client.run("install app/0.1@ --lockfile=conan.lock", assert_error=True)
            self.assertIn("Missing prebuilt package for 'app/0.1', 'pkg/0.1'", client.out)

        # Build one by one
        client.run("install {0} --lockfile=conan.lock --lockfile-out=conan.lock "
                   "--build={0}".format(build_order[0][0][0]))
        self.assertIn("dep/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        node = locked["3"]
        self.assertEqual(node.get("prev"), prev_dep)
        node = locked["2"]
        self.assertEqual(node.get("prev"), None)  # PREV is not defined yet, only exported
        node = locked["1"]
        self.assertEqual(node.get("prev"), None)  # PREV is not defined yet, only exported

        client.run("lock build-order conan.lock --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual(build_order[1:], jsonbo)

        client.run("install pkg/0.1@ --lockfile=conan.lock --build", assert_error=True)
        rrev = "#f3367e0e7d170aa12abccb175fee5f97" if client.cache.config.revisions_enabled else ""
        self.assertIn("Cannot build 'dep/0.1{}' because it is "
                      "already locked in the input lockfile".format(rrev), client.out)
        client.run("install {0} --lockfile=conan.lock --lockfile-out=conan.lock "
                   "--build={0}".format(build_order[1][0][0]))
        self.assertIn("dep/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("pkg/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        node = locked["3"]
        self.assertEqual(node.get("prev"), prev_dep)
        node = locked["2"]
        self.assertEqual(node.get("prev"), prev_pkg)
        node = locked["1"]
        self.assertEqual(node.get("prev"), None)  # PREV is not defined yet, only exported

        client.run("lock build-order conan.lock --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual(build_order[2:], jsonbo)

        client.run("install app/0.1@ --lockfile=conan.lock --build", assert_error=True)
        rrev = "#1364f701b47130c7e38f04c5e5fab985" if client.cache.config.revisions_enabled else ""
        self.assertIn("Cannot build 'pkg/0.1{}' because it is "
                      "already locked in the input lockfile".format(rrev), client.out)
        client.run("install {0} --lockfile=conan.lock --lockfile-out=conan.lock "
                   "--build={0}".format(build_order[2][0][0]))
        self.assertNotIn("dep/0.1", client.out)
        self.assertIn("pkg/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("app/0.1:a925a8281740e4cb4bcad9cf41ecc4c215210604 - Build", client.out)

        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        node = locked["3"]
        self.assertEqual(node.get("prev"), prev_dep)
        node = locked["2"]
        self.assertEqual(node.get("prev"), prev_pkg)
        node = locked["1"]
        self.assertEqual(node.get("prev"), prev_app)

        # New build order, nothing else to do
        client.run("lock build-order conan.lock --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual([], jsonbo)


class GraphLockWarningsTestCase(unittest.TestCase):

    def test_override(self):
        client = TestClient()
        client.save({"harfbuzz.py": GenConanfile("harfbuzz", "1.0"),
                     "ffmpeg.py": GenConanfile("ffmpeg", "1.0").with_requirement("harfbuzz/[>=1.0]"),
                     "meta.py": GenConanfile("meta", "1.0").with_requirement("ffmpeg/1.0")
                                                           .with_requirement("harfbuzz/1.0")
                     })
        client.run("export harfbuzz.py")
        client.run("export ffmpeg.py")
        client.run("export meta.py")

        # Building the graphlock we get the message
        client.run("lock create meta.py --lockfile-out=conan.lock")
        self.assertIn("WARN: ffmpeg/1.0: requirement harfbuzz/[>=1.0] overridden by meta/1.0"
                      " to harfbuzz/1.0", client.out)

        # Using the graphlock there is no warning message
        client.run("lock build-order conan.lock")
        self.assertNotIn("overridden", client.out)
        self.assertNotIn("WARN", client.out)


class GraphLockBuildRequireErrorTestCase(unittest.TestCase):

    def test_build_requires_should_be_locked(self):
        # https://github.com/conan-io/conan/issues/5807
        # this is the recommended approach, build_requires should be locked from the beginning
        client = TestClient()
        client.save({"zlib.py": GenConanfile(),
                     "harfbuzz.py": GenConanfile().with_require("fontconfig/1.0"),
                     "fontconfig.py": GenConanfile(),
                     "ffmpeg.py": GenConanfile().with_build_requires("fontconfig/1.0",
                                                                     "harfbuzz/1.0"),
                     "variant.py": GenConanfile().with_requires("ffmpeg/1.0",
                                                                "fontconfig/1.0",
                                                                "harfbuzz/1.0",
                                                                "zlib/1.0")
                     })
        client.run("export zlib.py zlib/1.0@")
        client.run("export fontconfig.py fontconfig/1.0@")
        client.run("export harfbuzz.py harfbuzz/1.0@")
        client.run("export ffmpeg.py ffmpeg/1.0@")

        # Building the graphlock we get the message
        client.run("lock create variant.py --build cascade --build outdated "
                   "--lockfile-out=conan.lock")

        if client.cache.config.revisions_enabled:
            fmpe = "ffmpeg/1.0#5522e93e2abfbd455e6211fe4d0531a2"
            font = "fontconfig/1.0#f3367e0e7d170aa12abccb175fee5f97"
            harf = "harfbuzz/1.0#3172f5e84120f235f75f8dd90fdef84f"
            zlib = "zlib/1.0#f3367e0e7d170aa12abccb175fee5f97"
            expected = [[['fontconfig/1.0@#f3367e0e7d170aa12abccb175fee5f97',
                          '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '2'],
                        ['zlib/1.0@#f3367e0e7d170aa12abccb175fee5f97',
                         '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '4']],
                        [['harfbuzz/1.0@#3172f5e84120f235f75f8dd90fdef84f',
                          'ea61889683885a5517800e8ebb09547d1d10447a', 'host', '3']],
                        [['ffmpeg/1.0@#5522e93e2abfbd455e6211fe4d0531a2',
                          '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '1']]]
        else:
            fmpe = "ffmpeg/1.0"
            font = "fontconfig/1.0"
            harf = "harfbuzz/1.0"
            zlib = "zlib/1.0"
            expected = [[['fontconfig/1.0@',
                          '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '2'],
                        ['zlib/1.0@',
                         '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '4']],
                        [['harfbuzz/1.0@',
                          'ea61889683885a5517800e8ebb09547d1d10447a', 'host', '3']],
                        [['ffmpeg/1.0@',
                          '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '1']]]

        lock1 = client.load("conan.lock")
        lock = json.loads(lock1)
        nodes = lock["graph_lock"]["nodes"]
        self.assertEqual(7, len(nodes))
        self.assertEqual(fmpe, nodes["1"]["ref"])
        self.assertEqual(["5", "6"], nodes["1"]["build_requires"])
        self.assertEqual(font, nodes["2"]["ref"])
        self.assertEqual(harf, nodes["3"]["ref"])
        self.assertEqual(zlib, nodes["4"]["ref"])
        self.assertEqual(font, nodes["5"]["ref"])
        self.assertEqual(harf, nodes["6"]["ref"])

        client.run("lock build-order conan.lock --json=bo.json")
        self.assertNotIn("cannot be found in lockfile", client.out)
        lock2 = client.load("conan.lock")
        self.assertEqual(lock2, lock1)
        build_order = json.loads(client.load("bo.json"))
        self.assertEqual(expected, build_order)

    def test_build_requires_not_needed(self):
        client = TestClient()
        client.save({'tool/conanfile.py': GenConanfile(),
                     'libA/conanfile.py': GenConanfile().with_build_requires("tool/1.0"),
                     'App/conanfile.py': GenConanfile().with_require("libA/1.0")})
        client.run("create tool tool/1.0@")
        client.run("create libA libA/1.0@")
        client.run("create App app/1.0@")

        # Create the full lock create
        client.run("lock create --reference=app/1.0@ --build --lockfile-out=conan.lock")
        lock = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        app = lock["1"]
        liba = lock["2"]
        tool = lock["3"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(app["ref"], "app/1.0#ac2e355bf59f54e838c9d2f1d8d1126c")
            self.assertEqual(liba["ref"], "libA/1.0#3fb401b4f9169fab06be253aa3fbcc1b")
            self.assertEqual(tool["ref"], "tool/1.0#f3367e0e7d170aa12abccb175fee5f97")
        else:
            self.assertEqual(app["ref"], "app/1.0")
            self.assertEqual(liba["ref"], "libA/1.0")
            self.assertEqual(tool["ref"], "tool/1.0")

        self.assertEqual(app["package_id"], "8a4d75100b721bfde375a978c780bf3880a22bab")
        self.assertIsNone(app.get("prev"))
        self.assertEqual(liba["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertIsNone(liba.get("prev"))
        self.assertEqual(tool["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertIsNone(tool.get("prev"))

        client.run("lock build-order conan.lock --json=bo.json")
        bo0 = client.load("bo.json")
        if client.cache.config.revisions_enabled:
            tool = "tool/1.0@#f3367e0e7d170aa12abccb175fee5f97"
            liba = "libA/1.0@#3fb401b4f9169fab06be253aa3fbcc1b"
            app = "app/1.0@#ac2e355bf59f54e838c9d2f1d8d1126c"
        else:
            tool = "tool/1.0@"
            liba = "libA/1.0@"
            app = "app/1.0@"
        expected = [
            [[tool, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", "host", "3"]],
            [[liba, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", "host", "2"]],
            [[app, "8a4d75100b721bfde375a978c780bf3880a22bab", "host", "1"]]
            ]
        self.assertEqual(expected, json.loads(bo0))

        client.run("create libA libA/2.0@ --lockfile=conan.lock", assert_error=True)
        self.assertIn("ERROR: Couldn't find 'libA/2.0' in lockfile", client.out)

        # Instead we export it and create a new lock create
        client.run("export libA libA/2.0@")
        client.run("lock create --reference=app/1.0@ --build=missing --lockfile-out=new.lock")
        new = client.load("new.lock")
        self.assertNotIn("libA/2.0", new)
        client.run("lock build-order new.lock --json=bo.json")
        self.assertEqual(json.loads(client.load("bo.json")), [])
