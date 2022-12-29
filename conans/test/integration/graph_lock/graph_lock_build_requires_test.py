import json
import textwrap
import unittest

from conans.client.tools.env import environment_append
from conans.test.utils.tools import TestClient, GenConanfile


class GraphLockBuildRequireTestCase(unittest.TestCase):

    def test_duplicated_build_require(self):
        t = TestClient()
        t.save({
            'br/conanfile.py': GenConanfile("br", "0.1"),
            'zlib/conanfile.py': GenConanfile("zlib", "0.1").with_build_requires("br/0.1"),
            'bzip2/conanfile.py': GenConanfile("bzip2", "0.1").with_build_requires("br/0.1"),
            'boost/conanfile.py': GenConanfile("boost", "0.1").with_require("zlib/0.1")
                                                              .with_require("bzip2/0.1")
                                                              .with_build_requires("br/0.1")
            })
        t.run("export br/conanfile.py")
        t.run("export zlib/conanfile.py")
        t.run("export bzip2/conanfile.py")

        # Create lock
        t.run("lock create boost/conanfile.py --build --lockfile-out=conan.lock")
        lock_json = json.loads(t.load("conan.lock"))
        br = lock_json["graph_lock"]["nodes"]["3"]
        self.assertIn("br/0.1", br["ref"])
        self.assertIsNone(br.get("prev"))

        # Compute build order
        t.run("lock build-order conan.lock --json=bo.json")
        if t.cache.config.revisions_enabled:
            expected = [[['br/0.1@#99b906c1d69c56560d0b12ff2b3d10c0',
                          '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '3']],
                        [['zlib/0.1@#1ce889ac4d50e301d4817064b4e4b6ee',
                          '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '1'],
                         ['bzip2/0.1@#ac5d76c1046b5effa212f7f69c409a0c',
                          '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '2']]]
        else:
            expected = [[['br/0.1@', '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '3']],
                        [['zlib/0.1@', '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '1'],
                         ['bzip2/0.1@', '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '2']]]
        self.assertEqual(expected, json.loads(t.load("bo.json")))

        # Create the first element of build order
        t.run("install br/0.1@ --lockfile=conan.lock --build=br/0.1")
        self.assertIn("br/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", t.out)
        self.assertIn("br/0.1: Created package revision", t.out)

    def test_package_both_contexts(self):
        t = TestClient()
        t.save({
            'protobuf/conanfile.py': GenConanfile("protobuf", "0.1"),
            'lib/conanfile.py': GenConanfile("lib", "0.1").with_require("protobuf/0.1")
                                                          .with_build_requires("protobuf/0.1"),
            'app/conanfile.py': GenConanfile("app", "0.1").with_require("lib/0.1")
        })
        t.run("export protobuf/conanfile.py")
        t.run("export lib/conanfile.py")
        t.run("export app/conanfile.py")

        # Create lock
        t.run("lock create app/conanfile.py --profile:build=default --profile:host=default --build"
              " --lockfile-out=conan.lock")
        lock_json = json.loads(t.load("conan.lock"))
        br = lock_json["graph_lock"]["nodes"]["3"]
        self.assertIn("protobuf/0.1", br["ref"])
        self.assertIsNone(br.get("prev"))

        # Compute build order
        t.run("lock build-order conan.lock --json=bo.json")
        if t.cache.config.revisions_enabled:
            expected = [[['protobuf/0.1@#a2f7b9ca9a4d2ebe512f9bc455802d34',
                          '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '2'],
                         ['protobuf/0.1@#a2f7b9ca9a4d2ebe512f9bc455802d34',
                          '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'build', '3']],
                        [['lib/0.1@#fe41709ab1369302057c10371e86213c',
                          '20bf540789ab45e970058c07c2360a66d6a77c55', 'host', '1']]]
        else:
            expected = [[['protobuf/0.1@',
                          '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '2'],
                         ['protobuf/0.1@',
                          '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'build', '3']],
                        [['lib/0.1@',
                          '20bf540789ab45e970058c07c2360a66d6a77c55', 'host', '1']]]
        self.assertEqual(expected, json.loads(t.load("bo.json")))

        # Create the first element of build order
        t.run("install protobuf/0.1@ --lockfile=conan.lock --build=protobuf")
        self.assertIn("protobuf/0.1: Created package revision", t.out)

    def test_package_different_id_both_contexts(self):
        t = TestClient()
        t.save({
            'protobuf/conanfile.py': GenConanfile("protobuf", "0.1").with_setting("os"),
            'lib/conanfile.py': GenConanfile("lib", "0.1").with_require("protobuf/0.1")
                                                          .with_build_requires("protobuf/0.1"),
            'app/conanfile.py': GenConanfile("app", "0.1").with_require("lib/0.1"),
            'Windows': "[settings]\nos=Windows",
            'Linux': "[settings]\nos=Linux"
        })
        t.run("export protobuf/conanfile.py")
        t.run("export lib/conanfile.py")
        t.run("export app/conanfile.py")

        # Create lock
        t.run("lock create app/conanfile.py --profile:build=Windows --profile:host=Linux --build"
              " --lockfile-out=conan.lock")

        lock_json = json.loads(t.load("conan.lock"))
        protobuf_build = lock_json["graph_lock"]["nodes"]["3"]
        self.assertIn("protobuf/0.1", protobuf_build["ref"])
        self.assertEqual(protobuf_build["package_id"], "3475bd55b91ae904ac96fde0f106a136ab951a5e")
        self.assertIsNone(protobuf_build.get("prev"))
        protobuf_host = lock_json["graph_lock"]["nodes"]["2"]
        self.assertIn("protobuf/0.1", protobuf_host["ref"])
        self.assertEqual(protobuf_host["package_id"], "cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31")
        self.assertIsNone(protobuf_host.get("prev"))

        # Compute build order
        t.run("lock build-order conan.lock --json=bo.json")
        if t.cache.config.revisions_enabled:
            expected = [[['protobuf/0.1@#d3d9079a0a15bb1a89922ed1a1070460',
                          'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31', 'host', '2'],
                         ['protobuf/0.1@#d3d9079a0a15bb1a89922ed1a1070460',
                          '3475bd55b91ae904ac96fde0f106a136ab951a5e', 'build', '3']],
                        [['lib/0.1@#fe41709ab1369302057c10371e86213c',
                          '20bf540789ab45e970058c07c2360a66d6a77c55', 'host', '1']]]
        else:
            expected = [[['protobuf/0.1@',
                          'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31', 'host', '2'],
                         ['protobuf/0.1@',
                          '3475bd55b91ae904ac96fde0f106a136ab951a5e', 'build', '3']],
                        [['lib/0.1@',
                          '20bf540789ab45e970058c07c2360a66d6a77c55', 'host', '1']]]
        self.assertEqual(expected, json.loads(t.load("bo.json")))

        # This works at the moment, but we don't know which node it is building
        t.run("install protobuf/0.1@ --lockfile=conan.lock --build=protobuf "
              "--lockfile-out=conan.lock")
        # FIXME: We need a way to speficy contexts or the ID of the node in the lockfile
        # FIXME: plus maybe the context too, to dissambiguate nodes in both contexts

    def test_build_require_not_removed(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . cmake/1.0@")
        client.save({"conanfile.py": GenConanfile().with_build_requires("cmake/1.0@")})
        client.run("create . flac/1.0@")
        client.run("lock create --reference=flac/1.0@ --lockfile-out=conan.lock --build")
        lock = json.loads(client.load("conan.lock"))
        flac = lock["graph_lock"]["nodes"]["1"]
        if client.cache.config.revisions_enabled:
            ref = "flac/1.0#98ed25e4bb9bc0fdc6d5266afa81f9cf"
            prev = "405174d701cf8c5478230a92bcc5cf75"
        else:
            ref = "flac/1.0"
            prev = "0"
        self.assertEqual(flac["ref"], ref)
        self.assertEqual(flac["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertIsNone(flac.get("prev"))

        client.run("install flac/1.0@ --lockfile=conan.lock --lockfile-out=output.lock")
        lock = json.loads(client.load("output.lock"))
        flac = lock["graph_lock"]["nodes"]["1"]
        self.assertEqual(flac["ref"], ref)
        self.assertEqual(flac["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertIsNone(flac.get("prev"))

        client.run("install flac/1.0@ --build=flac --lockfile=conan.lock --lockfile-out=output.lock")
        lock = json.loads(client.load("output.lock"))
        flac = lock["graph_lock"]["nodes"]["1"]
        self.assertEqual(flac["ref"], ref)
        self.assertEqual(flac["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(flac["prev"], prev)

    def test_multiple_matching_build_require(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . cmake/1.0@")
        client.run("create . cmake/1.1@")
        client.save({"conanfile.py": GenConanfile().with_build_requires("cmake/1.0")})
        client.run("create . pkg1/1.0@")
        client.save({"conanfile.py": GenConanfile().with_build_requires("cmake/1.1")
                                                   .with_require("pkg1/1.0")})
        client.run("create . pkg2/1.0@")
        client.run("lock create --reference=pkg2/1.0@ --build --lockfile-out=conan.lock")
        client.run("install cmake/[>=1.0]@ --lockfile=conan.lock", assert_error=True)
        self.assertIn("Version ranges not allowed in 'cmake/[>=1.0]' when using lockfiles",
                      client.out)
        client.run("install cmake/1.1@ --lockfile=conan.lock")
        self.assertIn("cmake/1.1 from local cache - Cache", client.out)

    def test_unused_build_requires(self):
        client = TestClient()
        # create build_requires tools
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . cmake/1.0@")
        client.run("create . gtest/1.0@")
        client.save({"conanfile.py": GenConanfile().with_build_requires("gtest/1.0"),
                     "myprofile": "[build_requires]\ncmake/1.0\n"})
        client.run("create . pkg1/1.0@ -pr=myprofile")
        client.save({"conanfile.py": GenConanfile().with_build_requires("gtest/1.0")
                                                   .with_require("pkg1/1.0")})
        client.run("create . pkg2/1.0@ -pr=myprofile")

        client.run("lock create --reference=pkg2/1.0@ --build --base --lockfile-out=base.lock "
                   "-pr=myprofile")
        client.run("lock create --reference=pkg2/1.0@ --build --lockfile=base.lock "
                   "--lockfile-out=conan.lock -pr=myprofile")

        client.run("install pkg2/1.0@ --build=pkg2/1.0 --lockfile=conan.lock")
        self.assertIn("cmake/1.0 from local cache - Cache", client.out)
        self.assertIn("gtest/1.0 from local cache - Cache", client.out)
        self.assertIn("pkg2/1.0: Applying build-requirement: cmake/1.0", client.out)
        self.assertIn("pkg2/1.0: Applying build-requirement: gtest/1.0", client.out)

    def test_conditional_env_var(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . dep_recipe/1.0@")
        client.run("create . dep_profile/1.0@")
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            import os
            class Pkg(ConanFile):
                def build_requirements(self):
                    if os.getenv("USE_DEP"):
                        self.build_requires("dep_recipe/1.0")
            """)
        client.save({"conanfile.py": conanfile,
                     "profile": "[build_requires]\ndep_profile/1.0"})
        with environment_append({"USE_DEP": "1"}):
            client.run("lock create conanfile.py --name=pkg --version=1.0 -pr=profile")
        lock = client.load("conan.lock")
        self.assertIn("dep_recipe/1.0", lock)
        self.assertIn("dep_profile/1.0", lock)

        client.run("create . pkg/1.0@ --lockfile=conan.lock", assert_error=True)
        self.assertIn("ERROR: 'pkg/1.0' locked requirement 'dep_recipe/1.0' not found", client.out)

    @staticmethod
    def test_test_package_build_require():
        # https://github.com/conan-io/conan/issues/8744
        client = TestClient()
        # create build_requires tools
        client.save({"cmake/conanfile.py": GenConanfile(),
                     "pkg/conanfile.py":
                         GenConanfile().with_build_requires("cmake/[>=1.0]"),
                     "pkg/test_package/conanfile.py":
                         GenConanfile().with_build_requires("cmake/[>=1.0]").with_test("pass"),
                     "consumer/conanfile.py":
                         GenConanfile().with_requires("pkg/[>=1.0]"),
                     })

        client.run("export cmake cmake/1.0@")
        client.run("export pkg pkg/1.0@")

        client.run("lock create consumer/conanfile.py --build --lockfile-out=conan.lock")
        lock_json = json.loads(client.load("conan.lock"))
        node = lock_json["graph_lock"]["nodes"]["0"]
        assert node.get("ref") is None
        assert "conanfile.py" in node.get("path")

        client.run("create pkg/conanfile.py pkg/1.0@  --build=missing --lockfile=conan.lock")
        assert "pkg/1.0 (test package): Applying build-requirement: cmake/1.0" in client.out
