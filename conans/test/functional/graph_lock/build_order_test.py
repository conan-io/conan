import json
import unittest

from parameterized import parameterized

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, GenConanfile


class GraphLockBuildOrderTest(unittest.TestCase):

    def single_consumer_test(self):
        # https://github.com/conan-io/conan/issues/5727
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("test4", "0.1")})
        client.run("graph lock . --build")
        client.run("graph build-order . --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual([], jsonbo)

    @parameterized.expand([(True,), (False,)])
    def build_not_locked_test(self, export):
        # https://github.com/conan-io/conan/issues/5727
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("test4", "0.1")})
        if export:
            client.run("export .")
            client.run("graph lock test4/0.1@")
        else:
            client.run("create .")
            client.run("graph lock test4/0.1@ --build=test4")
        if client.cache.config.revisions_enabled:
            ref = "test4/0.1#f876ec9ea0f44cb7adb1588e431b391a"
            prev = "92cf292e73488c3527dab5f5ba81b947"
        else:
            ref = "test4/0.1#0"
            prev = "0"
        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        test4 = locked["1"]
        self.assertEqual(test4["ref"], ref)
        self.assertEqual(test4["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(test4.get("prev"), None)  # PREV is not defined yet, only exported
        client.run("graph build-order . --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        expected = [[['1', ref + ':5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9']]]
        self.assertEqual(expected, jsonbo)
        client.run("install test4/0.1@ --lockfile --build")
        self.assertIn("test4/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        test4 = locked["1"]
        self.assertEqual(test4["ref"], ref)
        self.assertEqual(test4["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(test4["prev"], prev)

        # New build order, nothing else to do
        client.run("graph build-order . --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual([], jsonbo)

    def build_locked_error_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("test4", "0.1")})
        client.run("create .")
        client.run("graph lock test4/0.1@")
        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        test4 = locked["1"]
        if client.cache.config.revisions_enabled:
            ref = "test4/0.1#f876ec9ea0f44cb7adb1588e431b391a"
            prev = "92cf292e73488c3527dab5f5ba81b947"
        else:
            ref = "test4/0.1#0"
            prev = "0"
        self.assertEqual(test4["ref"], ref)
        self.assertEqual(test4["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(test4["prev"], prev)
        client.run("graph build-order . --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual([], jsonbo)
        # if we try to build anyway, error
        client.run("install test4/0.1@ --lockfile --build", assert_error=True)
        self.assertIn("Trying to build 'test4/0.1#f876ec9ea0f44cb7adb1588e431b391a', "
                      "but it is locked", client.out)

    @parameterized.expand([(True,), (False,)])
    def transitive_build_not_locked_test(self, export):
        # https://github.com/conan-io/conan/issues/5727
        client = TestClient()
        client.save({"dep/conanfile.py": GenConanfile(),
                     "pkg/conanfile.py": GenConanfile().with_require_plain("dep/0.1"),
                     "app/conanfile.py": GenConanfile().with_require_plain("pkg/0.1")})
        if export:
            client.run("export dep dep/0.1@")
            client.run("export pkg pkg/0.1@")
            client.run("export app app/0.1@")
            client.run("graph lock app/0.1@")
        else:
            client.run("create dep dep/0.1@")
            client.run("create pkg pkg/0.1@")
            client.run("create app app/0.1@")
            client.run("graph lock app/0.1@ --build")

        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        if client.cache.config.revisions_enabled:
            nodes = [("1", "app/0.1#5e0af887c3e9391c872773734ccd2ca0",
                      "745ccd40fd696b66b0cb160fd5251a533563bbb4"),
                     ("2", "pkg/0.1#447b56f0334b7e2a28aa86e218c8b3bd",
                      "0b3845ce7fd8c0b4e46566097797bd872cb5bcf6"),
                     ("3", "dep/0.1#f3367e0e7d170aa12abccb175fee5f97",
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")]
            prev_dep = "83c38d3b4e5f1b8450434436eec31b00"
            prev_pkg = "bcde0c25612a6d296cf2cab2c264054d"
            prev_app = "9f30558ce471f676e3e06b633aabcf99"
            build_order = [[["3", "dep/0.1@#f3367e0e7d170aa12abccb175fee5f97"]],
                           [["2", "pkg/0.1@#447b56f0334b7e2a28aa86e218c8b3bd"]],
                           [["1", "app/0.1@#5e0af887c3e9391c872773734ccd2ca0"]]]
        else:
            nodes = [("1", "app/0.1#0",
                      "745ccd40fd696b66b0cb160fd5251a533563bbb4"),
                     ("2", "pkg/0.1#0",
                      "0b3845ce7fd8c0b4e46566097797bd872cb5bcf6"),
                     ("3", "dep/0.1#0",
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")]
            prev_dep = "0"
            prev_pkg = "0"
            prev_app = "0"
            build_order = [[["3", "dep/0.1@"]],
                           [["2", "pkg/0.1@"]],
                           [["1", "app/0.1@"]]]

        for lockid, ref, package_id in nodes:
            node = locked[lockid]
            self.assertEqual(node["ref"], ref)
            self.assertEqual(node["package_id"], package_id)
            self.assertEqual(node.get("prev"), None)  # PREV is not defined yet, only exported

        client.run("graph build-order . --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual(build_order, jsonbo)

        # prev is None, --build needs to be explicit or it will fail
        client.run("install app/0.1@ --lockfile", assert_error=True)
        self.assertIn("Missing prebuilt package for 'app/0.1', 'dep/0.1', 'pkg/0.1'", client.out)

        # Build one by one
        client.run("install dep/0.1@ --lockfile --build")
        self.assertIn("dep/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        node = locked["3"]
        self.assertEqual(node.get("prev"), prev_dep)
        node = locked["2"]
        self.assertEqual(node.get("prev"), None)  # PREV is not defined yet, only exported
        node = locked["1"]
        self.assertEqual(node.get("prev"), None)  # PREV is not defined yet, only exported

        client.run("graph build-order . --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual(build_order[:2], jsonbo)

        client.run("install pkg/0.1@ --lockfile --build", assert_error=True)
        self.assertIn("Trying to build 'dep/0.1#f3367e0e7d170aa12abccb175fee5f97', but it is locked",
                      client.out)
        client.run("install pkg/0.1@ --lockfile --build=pkg")
        self.assertIn("dep/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("pkg/0.1:0b3845ce7fd8c0b4e46566097797bd872cb5bcf6 - Build", client.out)
        locked = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        node = locked["3"]
        self.assertEqual(node.get("prev"), prev_dep)
        node = locked["2"]
        self.assertEqual(node.get("prev"), prev_pkg)
        node = locked["1"]
        self.assertEqual(node.get("prev"), None)  # PREV is not defined yet, only exported

        client.run("graph build-order . --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual(build_order[:1], jsonbo)

        client.run("install app/0.1@ --lockfile --build", assert_error=True)
        self.assertIn("Trying to build 'dep/0.1#f3367e0e7d170aa12abccb175fee5f97', but it is locked",
                      client.out)
        client.run("install app/0.1@ --lockfile --build=app")
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
        client.run("graph build-order . --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        self.assertEqual([], jsonbo)

    """def build_order_build_requires_test(self):
        # https://github.com/conan-io/conan/issues/5474
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . CA/1.0@user/channel")
        client.save({"conanfile.py": GenConanfile().with_build_require_plain("CA/1.0@user/channel")})
        client.run("create . CB/1.0@user/channel")

        consumer = textwrap.dedent('''
            [requires]
            CA/1.0@user/channel
            CB/1.0@user/channel
        ''')
        client.save({"conanfile.txt": consumer})
        client.run("graph lock conanfile.txt --build")
        client.run("graph build-order . --build --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        level0 = jsonbo[0]
        ca = level0[0]
        self.assertEqual("CA/1.0@user/channel#f3367e0e7d170aa12abccb175fee5f97"
                         ":5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", ca[1])
        level1 = jsonbo[1]
        cb = level1[0]
        self.assertEqual("CB/1.0@user/channel#29352c82c9c6b7d1be85524ef607f77f"
                         ":5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", cb[1])

    def package_revision_mode_build_order_test(self):
        # https://github.com/conan-io/conan/issues/6232
        client = TestClient()
        client.run("config set general.default_package_id_mode=package_revision_mode")
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . libb/0.1@")
        client.run("export . libc/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("libc/0.1")})
        client.run("export . liba/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("liba/0.1")
                                                   .with_require_plain("libb/0.1")})
        client.run("export . app/0.1@")

        client.run("graph lock app/0.1@ --build=missing")
        client.run("graph build-order . --build=missing --json=bo.json")
        self.assertIn("app/0.1:Package_ID_unknown - Unknown", client.out)
        self.assertIn("liba/0.1:Package_ID_unknown - Unknown", client.out)
        self.assertIn("libb/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        self.assertIn("libc/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        bo = client.load("bo.json")
        build_order = json.loads(bo)
        expected = [
            # First level
            [['3',
              'libc/0.1#f3367e0e7d170aa12abccb175fee5f97:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9']],
            # second level
            [['2', 'liba/0.1#7086607aa6efbad8e2527748e3ee8237:Package_ID_unknown'],
             ['4',
              'libb/0.1#f3367e0e7d170aa12abccb175fee5f97:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9']],
            # last level to build
            [['1', 'app/0.1#7742ee9e2f19af4f9ed7619f231ca871:Package_ID_unknown']]
        ]
        self.assertEqual(build_order, expected)"""


class GraphLockWarningsTestCase(unittest.TestCase):

    def test_override(self):
        client = TestClient()
        harfbuzz_ref = ConanFileReference.loads("harfbuzz/1.0")
        ffmpeg_ref = ConanFileReference.loads("ffmpeg/1.0")
        client.save({"harfbuzz.py": GenConanfile().with_name("harfbuzz").with_version("1.0"),
                     "ffmpeg.py": GenConanfile().with_name("ffmpeg").with_version("1.0")
                                                .with_requirement_plain("harfbuzz/[>=1.0]"),
                     "meta.py": GenConanfile().with_name("meta").with_version("1.0")
                                              .with_requirement(ffmpeg_ref)
                                              .with_requirement(harfbuzz_ref)
                     })
        client.run("export harfbuzz.py")
        client.run("export ffmpeg.py")
        client.run("export meta.py")

        # Building the graphlock we get the message
        client.run("graph lock meta.py")
        self.assertIn("WARN: ffmpeg/1.0: requirement harfbuzz/[>=1.0] overridden by meta/1.0"
                      " to harfbuzz/1.0", client.out)

        # Using the graphlock there is no warning message
        client.run("graph build-order conan.lock")
        self.assertNotIn("overridden", client.out)
        self.assertNotIn("WARN", client.out)


class GraphLockBuildRequireErrorTestCase(unittest.TestCase):

    def test_not_locked_build_requires(self):
        # https://github.com/conan-io/conan/issues/5807
        # even if the build requires are not locked, the graph can be augmented to add them
        client = TestClient()
        client.save({"zlib.py": GenConanfile(),
                     "harfbuzz.py": GenConanfile().with_require_plain("fontconfig/1.0"),
                     "fontconfig.py": GenConanfile(),
                     "ffmpeg.py": GenConanfile().with_build_require_plain("fontconfig/1.0")
                                                .with_build_require_plain("harfbuzz/1.0"),
                     "variant.py": GenConanfile().with_require_plain("ffmpeg/1.0")
                                                 .with_require_plain("fontconfig/1.0")
                                                 .with_require_plain("harfbuzz/1.0")
                                                 .with_require_plain("zlib/1.0")
                     })
        client.run("export zlib.py zlib/1.0@")
        client.run("export fontconfig.py fontconfig/1.0@")
        client.run("export harfbuzz.py harfbuzz/1.0@")
        client.run("export ffmpeg.py ffmpeg/1.0@")

        # Building the graphlock we get the message
        client.run("graph lock variant.py")
        fmpe = "ffmpeg/1.0#5522e93e2abfbd455e6211fe4d0531a2"
        fmpe_id = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        font = "fontconfig/1.0#f3367e0e7d170aa12abccb175fee5f97"
        font_id = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        harf = "harfbuzz/1.0#3172f5e84120f235f75f8dd90fdef84f"
        harf_id = "ea61889683885a5517800e8ebb09547d1d10447a"
        zlib = "zlib/1.0#f3367e0e7d170aa12abccb175fee5f97:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        lock = json.loads(client.load("conan.lock"))
        nodes = lock["graph_lock"]["nodes"]
        self.assertEqual(5, len(nodes))
        self.assertEqual(fmpe, nodes["1"]["ref"])
        self.assertEqual(fmpe_id, nodes["1"]["package_id"])
        self.assertEqual(font, nodes["2"]["ref"])
        self.assertEqual(font_id, nodes["2"]["package_id"])
        self.assertEqual(harf, nodes["3"]["ref"])
        self.assertEqual(harf_id, nodes["3"]["package_id"])
        self.assertEqual(zlib, nodes["4"]["ref"])

        client.run("config set general.relax_lockfile=1")
        client.run("graph build-order . --build cascade --build outdated --json=bo.json")
        self.assertIn("ffmpeg/1.0: WARN: Build-require 'fontconfig' cannot be found in lockfile",
                      client.out)
        self.assertIn("ffmpeg/1.0: WARN: Build-require 'harfbuzz' cannot be found in lockfile",
                      client.out)
        lock = json.loads(client.load("conan.lock"))
        nodes = lock["graph_lock"]["nodes"]
        self.assertEqual(5, len(nodes))
        self.assertEqual(fmpe, nodes["1"]["pref"])
        # The lockfile doesn't add build_requires
        self.assertEqual(None, nodes["1"].get("build_requires"))
        self.assertEqual(font, nodes["2"]["pref"])
        self.assertEqual(harf, nodes["3"]["pref"])
        self.assertEqual(zlib, nodes["4"]["pref"])

        build_order = json.loads(client.load("bo.json"))
        self.assertEqual([["5", font]], build_order[0])
        self.assertEqual([["6", harf]], build_order[1])
        self.assertEqual([["1", fmpe], ["4", zlib]], build_order[2])

    def test_build_requires_should_be_locked(self):
        # https://github.com/conan-io/conan/issues/5807
        # this is the recommended approach, build_requires should be locked from the beginning
        client = TestClient()
        client.save({"zlib.py": GenConanfile(),
                     "harfbuzz.py": GenConanfile().with_require_plain("fontconfig/1.0"),
                     "fontconfig.py": GenConanfile(),
                     "ffmpeg.py": GenConanfile().with_build_require_plain("fontconfig/1.0")
                                                .with_build_require_plain("harfbuzz/1.0"),
                     "variant.py": GenConanfile().with_require_plain("ffmpeg/1.0")
                                                 .with_require_plain("fontconfig/1.0")
                                                 .with_require_plain("harfbuzz/1.0")
                                                 .with_require_plain("zlib/1.0")
                     })
        client.run("export zlib.py zlib/1.0@")
        client.run("export fontconfig.py fontconfig/1.0@")
        client.run("export harfbuzz.py harfbuzz/1.0@")
        client.run("export ffmpeg.py ffmpeg/1.0@")

        # Building the graphlock we get the message
        client.run("graph lock variant.py --build")
        fmpe = "ffmpeg/1.0#5522e93e2abfbd455e6211fe4d0531a2:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        font = "fontconfig/1.0#f3367e0e7d170aa12abccb175fee5f97:"\
               "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        harf = "harfbuzz/1.0#3172f5e84120f235f75f8dd90fdef84f:"\
               "ea61889683885a5517800e8ebb09547d1d10447a"
        zlib = "zlib/1.0#f3367e0e7d170aa12abccb175fee5f97:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        lock = json.loads(client.load("conan.lock"))
        nodes = lock["graph_lock"]["nodes"]
        self.assertEqual(7, len(nodes))
        self.assertEqual(fmpe, nodes["1"]["pref"])
        self.assertEqual(["5", "6"], nodes["1"]["build_requires"])
        self.assertEqual(font, nodes["2"]["pref"])
        self.assertEqual(harf, nodes["3"]["pref"])
        self.assertEqual(zlib, nodes["4"]["pref"])
        self.assertEqual(font, nodes["5"]["pref"])
        self.assertEqual(harf, nodes["6"]["pref"])

        client.run("graph build-order . --build cascade --build outdated --json=bo.json")
        self.assertNotIn("cannot be found in lockfile", client.out)
        lock = json.loads(client.load("conan.lock"))
        nodes = lock["graph_lock"]["nodes"]
        self.assertEqual(7, len(nodes))
        self.assertEqual(fmpe, nodes["1"]["pref"])
        self.assertEqual(["5", "6"], nodes["1"]["build_requires"])
        self.assertEqual(font, nodes["2"]["pref"])
        self.assertEqual(harf, nodes["3"]["pref"])
        self.assertEqual(zlib, nodes["4"]["pref"])
        self.assertEqual(font, nodes["5"]["pref"])
        self.assertEqual(harf, nodes["6"]["pref"])

        build_order = json.loads(client.load("bo.json"))
        self.assertEqual([["5", font]], build_order[0])
        self.assertEqual([["6", harf]], build_order[1])
        self.assertEqual([["1", fmpe], ["4", zlib]], build_order[2])


class GraphLockBuildRequiresNotNeeded(unittest.TestCase):

    def test_build_requires_not_needed(self):
        client = TestClient()
        client.save({'tool/conanfile.py': GenConanfile(),
                     'libA/conanfile.py': GenConanfile().with_build_require_plain("tool/1.0"),
                     'App/conanfile.py': GenConanfile().with_require_plain("libA/1.0")})
        client.run("create tool tool/1.0@")
        client.run("create libA libA/1.0@")
        client.run("create App app/1.0@")

        # Create the full graph lock
        client.run("graph lock app/1.0@ --build")
        lock = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        app = lock["1"]
        self.assertEqual(app["ref"], "app/1.0#ac2e355bf59f54e838c9d2f1d8d1126c")
        self.assertEqual(app["package_id"], "8a4d75100b721bfde375a978c780bf3880a22bab")
        self.assertIsNone(app.get("prev"))
        liba = lock["2"]
        self.assertEqual(liba["ref"], "libA/1.0#3fb401b4f9169fab06be253aa3fbcc1b")
        self.assertEqual(liba["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertIsNone(liba.get("prev"))
        tool = lock["3"]
        self.assertEqual(tool["ref"], "tool/1.0#f3367e0e7d170aa12abccb175fee5f97")
        self.assertEqual(tool["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertIsNone(tool.get("prev"))

        client.run("graph build-order . --json=bo.json")
        bo0 = client.load("bo.json")
        tool = "tool/1.0#f3367e0e7d170aa12abccb175fee5f97:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        liba = "libA/1.0#3fb401b4f9169fab06be253aa3fbcc1b:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        app = "app/1.0#ac2e355bf59f54e838c9d2f1d8d1126c:8a4d75100b721bfde375a978c780bf3880a22bab"
        expected = [
            [["3", tool]],
            [["2", liba]],
            [["1", app]]
            ]
        self.assertEqual(expected, json.loads(bo0))
        # FIXME: This libA/2.0 is NOT required by the app
        client.run("create libA libA/2.0@ --lockfile")
        lock = json.loads(client.load("conan.lock"))["graph_lock"]["nodes"]
        app = lock["1"]
        self.assertEqual(app["ref"], "app/1.0#ac2e355bf59f54e838c9d2f1d8d1126c")
        self.assertEqual(app["package_id"], "8a4d75100b721bfde375a978c780bf3880a22bab")
        self.assertIsNone(app.get("prev"))
        liba = lock["2"]
        self.assertEqual(liba["ref"], "libA/1.0#3fb401b4f9169fab06be253aa3fbcc1b")
        self.assertEqual(liba["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(liba["prev"], )
        tool = lock["3"]
        self.assertEqual(tool["ref"], "tool/1.0#f3367e0e7d170aa12abccb175fee5f97")
        self.assertEqual(tool["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertIsNone(tool.get("prev"))

        client.run("graph build-order . --json=bo.json")
        bo1 = client.load("bo.json")
        print(bo1)
        client.run("graph build-order . --json=bo.json")
        self.assertEqual(bo1, client.load("bo.json"))
