import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class TransitiveIdsTest(unittest.TestCase):

    def transitive_header_only_test(self):
        # https://github.com/conan-io/conan/issues/6450
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_version_mode")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/1.0@")
        client.run("create . liba/2.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("liba/1.0")
                                                   .with_package_id("self.info.header_only()")})
        client.run("create . libb/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("libb/1.0")})
        client.run("create . libc/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("libc/1.0")
                                                   .with_require_plain("liba/1.0")})
        client.run("create . libd/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("libc/1.0")
                                                   .with_require_plain("liba/2.0")})
        client.run("create . libd/1.0@", assert_error=True)
        self.assertIn("liba/2.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libb/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libc/1.0:bfa6c8f046896806f65c8fe554bd57f235b101e8 - Missing", client.out)

    def transitive_library_test(self):
        # https://github.com/conan-io/conan/issues/6450
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_version_mode")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/1.0@")
        client.run("create . liba/2.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("liba/1.0")})
        client.run("create . libb/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("libb/1.0")})
        client.run("create . libc/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("libc/1.0")
                                                   .with_require_plain("liba/1.0")})
        client.run("create . libd/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("libc/1.0")
                                                   .with_require_plain("liba/2.0")})
        client.run("create . libd/1.0@", assert_error=True)
        self.assertIn("liba/2.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libb/1.0:e71235a6f57633221a2b85f9b6aca14cda69e1fd - Missing", client.out)
        self.assertIn("libc/1.0:aca59dcd0ac1b8d3ff415be731f32789b722651e - Missing", client.out)

    def transitive_unrelated_test(self):
        # https://github.com/conan-io/conan/issues/6450
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_version_mode")
        # LibA
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/1.0@")
        client.run("create . liba/2.0@")
        # libB -> LibA
        client.save({"conanfile.py": GenConanfile().with_require_plain("liba/1.0")})
        client.run("create . libb/1.0@")
        # libC -> libB
        unrelated = "self.info.requires['libb'].unrelated_mode()"
        # unrelated = "self.info.requires.unrelated_mode()"
        client.save({"conanfile.py": GenConanfile().with_require_plain("libb/1.0")
                                                   .with_package_id(unrelated)})
        client.run("create . libc/1.0@")
        # LibD -> LibC
        client.save({"conanfile.py": GenConanfile().with_require_plain("libc/1.0")})
        client.run("create . libd/1.0@")
        # LibE -> LibD, LibA/2.0
        client.save({"conanfile.py": GenConanfile().with_require_plain("libd/1.0")
                                                   .with_require_plain("liba/2.0")})
        client.run("create . libe/1.0@", assert_error=True)
        self.assertIn("liba/2.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libb/1.0:e71235a6f57633221a2b85f9b6aca14cda69e1fd - Missing", client.out)
        self.assertIn("libc/1.0:e3884c6976eb7debb8ec57aada7c0c2beaabe8ac - Missing", client.out)
        self.assertIn("libd/1.0:9b0b7b0905c9bc2cb9b7329f842b3b7c6663e8c3 - Missing", client.out)

    def transitive_full_unrelated_test(self):
        # https://github.com/conan-io/conan/issues/6450
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_version_mode")
        # LibA
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/1.0@")
        client.run("create . liba/2.0@")
        # libB -> LibA
        client.save({"conanfile.py": GenConanfile().with_require_plain("liba/1.0")})
        client.run("create . libb/1.0@")
        # libC -> libB
        unrelated = "self.info.requires.unrelated_mode()"
        client.save({"conanfile.py": GenConanfile().with_require_plain("libb/1.0")
                    .with_package_id(unrelated)})
        client.run("create . libc/1.0@")
        # LibD -> LibC
        client.save({"conanfile.py": GenConanfile().with_require_plain("libc/1.0")})
        client.run("create . libd/1.0@")
        # LibE -> LibD, LibA/2.0
        client.save({"conanfile.py": GenConanfile().with_require_plain("libd/1.0")
                    .with_require_plain("liba/2.0")})
        client.run("create . libe/1.0@", assert_error=True)
        self.assertIn("liba/2.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libb/1.0:e71235a6f57633221a2b85f9b6aca14cda69e1fd - Missing", client.out)
        self.assertIn("libc/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        # Old behavior would have LibD binary in cache
        # self.assertIn("libd/1.0:119e0b2903330cef59977f8976cb82a665b510c1 - Cache", client.out)
        # VS. NEW BEHAVIOR AFTER BUGFIX, it is missing
        self.assertIn("libd/1.0:95b14a919aa70f9a7e24afbf48d1101cff344a67 - Missing", client.out)

    def transitive_second_level_header_only_test(self):
        # https://github.com/conan-io/conan/issues/6450
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_version_mode")
        # LibA
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/1.0@")
        client.run("create . liba/2.0@")
        # libB -> LibA
        client.save({"conanfile.py": GenConanfile().with_require_plain("liba/1.0")})
        client.run("create . libb/1.0@")
        # libC -> libB

        unrelated = "self.info.header_only()"
        client.save({"conanfile.py": GenConanfile().with_require_plain("libb/1.0")
                                                   .with_package_id(unrelated)})
        client.run("create . libc/1.0@")
        # LibD -> LibC
        client.save({"conanfile.py": GenConanfile().with_require_plain("libc/1.0")})
        client.run("create . libd/1.0@")
        self.assertIn("libc/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)

        # LibE -> LibD, LibA/2.0
        client.save({"conanfile.py": GenConanfile().with_require_plain("libd/1.0")
                                                   .with_require_plain("liba/2.0")})
        client.run("create . libe/1.0@", assert_error=True)
        self.assertIn("liba/2.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libb/1.0:e71235a6f57633221a2b85f9b6aca14cda69e1fd - Missing", client.out)
        self.assertIn("libc/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libd/1.0:95b14a919aa70f9a7e24afbf48d1101cff344a67 - Missing", client.out)
