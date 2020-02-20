import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class TransitiveIdsTest(unittest.TestCase):

    def transitive_library_test(self):
        # https://github.com/conan-io/conan/issues/6450
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_version_mode")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/1.0@")
        client.run("create . liba/1.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("liba/1.0")})
        client.run("create . libb/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("libb/1.0")})
        client.run("create . libc/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("libc/1.0")
                                                   .with_require_plain("liba/1.0")})
        client.run("create . libd/1.0@")
        # The consumer forces to depend on liba/2, instead of liba/1
        client.save({"conanfile.py": GenConanfile().with_require_plain("libc/1.0")
                                                   .with_require_plain("liba/1.1")})
        client.run("create . libd/1.0@", assert_error=True)
        # both B and C require a new binary
        self.assertIn("liba/1.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libb/1.0:50b928d46d42051a461440161b017eb6d52e2dff - Missing", client.out)
        self.assertIn("libc/1.0:4599994f77257f88443590022af4754d5520b753 - Missing", client.out)
        self.assertIn("libd/1.0:39906c34335d9ad465711e847688c4a27894af0f - Build", client.out)

    def transitive_major_mode_test(self):
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
        client.save({"conanfile.py": GenConanfile().with_require_plain("liba/1.0")})
        client.run("create . libb/1.0@")
        # libC -> libB
        major_mode = "self.info.requires.major_mode()"
        client.save({"conanfile.py": GenConanfile().with_require_plain("libb/1.0")
                                                   .with_package_id(major_mode)})
        client.run("create . libc/1.0@")
        # Check the LibC ref with RREV keeps the same
        self.assertIn("libc/1.0:3627c16569f55501cb7d6c5db2b4b00faec7caf6 - Build", client.out)
        # LibD -> LibC
        client.save({"conanfile.py": GenConanfile().with_require_plain("libc/1.0")})
        client.run("create . libd/1.0@")
        # LibE -> LibD, LibA/2.0
        client.save({"conanfile.py": GenConanfile().with_require_plain("libd/1.0")
                                                   .with_require_plain("liba/1.1")})
        client.run("create . libe/1.0@", assert_error=True)
        self.assertIn("liba/1.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("libb/1.0:50b928d46d42051a461440161b017eb6d52e2dff - Missing", client.out)
        # Check the LibC ref with RREV keeps the same, it is in cache, not missing
        self.assertIn("libc/1.0:3627c16569f55501cb7d6c5db2b4b00faec7caf6 - Cache", client.out)
        # But LibD package ID changes and is missing, because it depends transitively on LibA
        self.assertIn("libd/1.0:39906c34335d9ad465711e847688c4a27894af0f - Missing", client.out)
        self.assertIn("libe/1.0:204261ad030cca3acf07c7a58b169e4257056ba1 - Build", client.out)
