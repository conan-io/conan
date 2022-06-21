import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class TransitiveIdsTest(unittest.TestCase):

    def test_transitive_library(self):
        # https://github.com/conan-io/conan/issues/6450
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_version_mode")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/1.0@")
        client.run("create . liba/1.1@")
        client.save({"conanfile.py": GenConanfile().with_require("liba/1.0")})
        client.run("create . libb/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("libb/1.0")})
        client.run("create . libc/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("libc/1.0")
                                                   .with_require("liba/1.0")})
        client.run("create . libd/1.0@")
        # The consumer forces to depend on liba/2, instead of liba/1
        client.save({"conanfile.py": GenConanfile().with_require("libc/1.0")
                                                   .with_require("liba/1.1")})
        client.run("create . libd/1.0@", assert_error=True)
        # both B and C require a new binary
        self.assertIn("liba/1.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libb/1.0:50b928d46d42051a461440161b017eb6d52e2dff - Missing", client.out)
        self.assertIn("libc/1.0:4599994f77257f88443590022af4754d5520b753 - Missing", client.out)
        self.assertIn("libd/1.0:39906c34335d9ad465711e847688c4a27894af0f - Build", client.out)

    def test_transitive_major_mode(self):
        # https://github.com/conan-io/conan/issues/6450
        # Test LibE->LibD->LibC->LibB->LibA
        # LibC declares that it only depends on major version changes of its upstream
        # So LibC package ID doesn't change, even if LibA changes
        # But LibD package ID changes, even if its direct dependency LibC doesn't
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_version_mode")
        # LibA
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/1.0@")
        client.run("create . liba/1.1@")
        # libB -> LibA
        client.save({"conanfile.py": GenConanfile().with_require("liba/1.0")})
        client.run("create . libb/1.0@")
        # libC -> libB
        major_mode = "self.info.requires.major_mode()"
        client.save({"conanfile.py": GenConanfile().with_require("libb/1.0")
                                                   .with_package_id(major_mode)})
        client.run("create . libc/1.0@")
        # Check the LibC ref with RREV keeps the same
        self.assertIn("libc/1.0:3627c16569f55501cb7d6c5db2b4b00faec7caf6 - Build", client.out)
        # LibD -> LibC
        client.save({"conanfile.py": GenConanfile().with_require("libc/1.0")})
        client.run("create . libd/1.0@")
        # LibE -> LibD, LibA/2.0
        client.save({"conanfile.py": GenConanfile().with_require("libd/1.0")
                                                   .with_require("liba/1.1")})
        client.run("create . libe/1.0@", assert_error=True)
        self.assertIn("liba/1.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libb/1.0:50b928d46d42051a461440161b017eb6d52e2dff - Missing", client.out)
        # Check the LibC ref with RREV keeps the same, it is in cache, not missing
        self.assertIn("libc/1.0:3627c16569f55501cb7d6c5db2b4b00faec7caf6 - Cache", client.out)
        # But LibD package ID changes and is missing, because it depends transitively on LibA
        self.assertIn("libd/1.0:39906c34335d9ad465711e847688c4a27894af0f - Missing", client.out)
        self.assertIn("libe/1.0:204261ad030cca3acf07c7a58b169e4257056ba1 - Build", client.out)

    def test_transitive_unrelated(self):
        # https://github.com/conan-io/conan/issues/6450
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_version_mode")
        # LibA
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/1.0@")
        client.run("create . liba/2.0@")
        # libB -> LibA
        client.save({"conanfile.py": GenConanfile().with_require("liba/1.0")})
        client.run("create . libb/1.0@")
        # libC -> libB
        unrelated = "self.info.requires['libb'].unrelated_mode()"
        client.save({"conanfile.py": GenConanfile().with_require("libb/1.0")
                    .with_package_id(unrelated)})
        client.run("create . libc/1.0@")
        # LibD -> LibC
        client.save({"conanfile.py": GenConanfile().with_require("libc/1.0")})
        client.run("create . libd/1.0@")
        # LibE -> LibD, LibA/2.0
        client.save({"conanfile.py": GenConanfile().with_require("libd/1.0")
                    .with_require("liba/2.0")})
        client.run("create . libe/1.0@", assert_error=True)
        self.assertIn("liba/2.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libb/1.0:e71235a6f57633221a2b85f9b6aca14cda69e1fd - Missing", client.out)
        self.assertIn("libc/1.0:e3884c6976eb7debb8ec57aada7c0c2beaabe8ac - Missing", client.out)
        self.assertIn("libd/1.0:9b0b7b0905c9bc2cb9b7329f842b3b7c6663e8c3 - Missing", client.out)

    def test_transitive_second_level_header_only(self):
        # https://github.com/conan-io/conan/issues/6450
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_version_mode")
        # LibA
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/1.0@")
        client.run("create . liba/2.0@")
        # libB -> LibA
        client.save({"conanfile.py": GenConanfile().with_require("liba/1.0")})
        client.run("create . libb/1.0@")
        # libC -> libB

        unrelated = "self.info.clear()"
        client.save({"conanfile.py": GenConanfile().with_require("libb/1.0")
                                                   .with_package_id(unrelated)})
        client.run("create . libc/1.0@")
        # LibD -> LibC
        client.save({"conanfile.py": GenConanfile().with_require("libc/1.0")})
        client.run("create . libd/1.0@")
        self.assertIn("libc/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)

        # LibE -> LibD, LibA/2.0
        client.save({"conanfile.py": GenConanfile().with_require("libd/1.0")
                                                   .with_require("liba/2.0")})
        client.run("create . libe/1.0@", assert_error=True)  # LibD is NOT missing!
        self.assertIn("libd/1.0:119e0b2903330cef59977f8976cb82a665b510c1 - Cache", client.out)
        # USE THE NEW FIXED PACKAGE_ID
        client.run("config set general.full_transitive_package_id=1")
        client.run("create . libe/1.0@", assert_error=True)
        self.assertIn("liba/2.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libb/1.0:e71235a6f57633221a2b85f9b6aca14cda69e1fd - Missing", client.out)
        self.assertIn("libc/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libd/1.0:95b14a919aa70f9a7e24afbf48d1101cff344a67 - Missing", client.out)

    def test_transitive_header_only(self):
        # https://github.com/conan-io/conan/issues/6450
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_version_mode")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/1.0@")
        client.run("create . liba/2.0@")
        client.save({"conanfile.py": GenConanfile().with_require("liba/1.0")
                                                   .with_package_id("self.info.header_only()")})
        client.run("create . libb/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("libb/1.0")})
        client.run("create . libc/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("libc/1.0")
                                                   .with_require("liba/1.0")})
        client.run("create . libd/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("libc/1.0")
                                                   .with_require("liba/2.0")})

        client.run("create . libd/1.0@")  # Doesn't complain it is missing a binary!
        self.assertIn(" libc/1.0:fd60a00caf13b07bfce8690315c9e953aafd664b - Cache", client.out)
        # USE THE NEW FIXED PACKAGE_ID
        client.run("config set general.full_transitive_package_id=1")
        client.run("create . libd/1.0@", assert_error=True)
        self.assertIn("liba/2.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libb/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libc/1.0:bfa6c8f046896806f65c8fe554bd57f235b101e8 - Missing", client.out)
