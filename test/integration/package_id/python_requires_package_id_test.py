import textwrap
import unittest

from conan.test.utils.tools import TestClient, GenConanfile
from conans.util.files import save


PKG_ID_1 = "47b42eaf657374a3d040394f03961b66c53bda5e"
PKG_ID_2 = "8b7006bf91e5b52cc1ac24a7a4d9c326ee954bb2"


class PythonRequiresPackageIDTest(unittest.TestCase):

    def setUp(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=tool --version=1.1.1")
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                python_requires ="tool/[*]"
            """)
        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": conanfile})
        self.client = client
        self.client2 = client2

    def test_default(self):
        self.client2.run("create . --name=pkg --version=0.1")
        self.assertIn("tool/1.1.1", self.client2.out)
        pkg_id = "170e82ef3a6bf0bbcda5033467ab9d7805b11d0b"
        self.client2.assert_listed_binary({"pkg/0.1": (pkg_id,
                                                       "Build")})

        self.client.run("export . --name=tool --version=1.1.2")
        self.client2.run("create . --name=pkg --version=0.1")
        self.assertIn("tool/1.1.2", self.client2.out)
        self.client2.assert_listed_binary({"pkg/0.1": (pkg_id,
                                                       "Build")})

        # With a minor change, it fires a rebuild
        self.client.run("export . --name=tool --version=1.2.0")
        self.client2.run("create . --name=pkg --version=0.1")
        self.assertIn("tool/1.2.0", self.client2.out)
        self.client2.assert_listed_binary({"pkg/0.1": ("5eb1e7ea93fdd67fe3c3b166d240844648ba2b7a",
                                                       "Build")})

    def test_change_mode_conf(self):
        # change the policy in conan.conf
        save(self.client2.cache.new_config_path, "core.package_id:default_python_mode=patch_mode")
        self.client2.run("create . --name=pkg --version=0.1")
        self.assertIn("tool/1.1.1", self.client2.out)
        self.client2.assert_listed_binary({"pkg/0.1": (PKG_ID_1,
                                                       "Build")})

        # with a patch change, new ID
        self.client.run("export . --name=tool --version=1.1.2")
        self.client2.run("create . --name=pkg --version=0.1")
        self.assertIn("tool/1.1.2", self.client2.out)
        self.client2.assert_listed_binary({"pkg/0.1": (PKG_ID_2,
                                                       "Build")})

    def test_unrelated_conf(self):
        # change the policy in conan.conf
        save(self.client2.cache.new_config_path,
             "core.package_id:default_python_mode=unrelated_mode")
        self.client2.run("create . --name=pkg --version=0.1")
        self.assertIn("tool/1.1.1", self.client2.out)
        pkg_id = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
        self.client2.assert_listed_binary({"pkg/0.1": (pkg_id,
                                                       "Build")})

        # with any change the package id doesn't change
        self.client.run("export . --name=tool --version=1.1.2")
        self.client2.run("create . --name=pkg --version=0.1 --build missing")
        self.assertIn("tool/1.1.2", self.client2.out)
        self.client2.assert_listed_binary({"pkg/0.1": (pkg_id,
                                                       "Cache")})

    def test_change_mode_package_id(self):
        # change the policy in package_id
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                python_requires ="tool/[*]"
                def package_id(self):
                    self.info.python_requires.patch_mode()
            """)
        self.client2.save({"conanfile.py": conanfile})
        self.client2.run("create . --name=pkg --version=0.1")
        self.assertIn("tool/1.1.1", self.client2.out)
        self.client2.assert_listed_binary({"pkg/0.1": (PKG_ID_1,
                                                       "Build")})

        # with a patch change, new ID
        self.client.run("export . --name=tool --version=1.1.2")
        self.client2.run("create . --name=pkg --version=0.1")
        self.assertIn("tool/1.1.2", self.client2.out)
        self.client2.assert_listed_binary({"pkg/0.1": (PKG_ID_2,
                                                       "Build")})


class PythonRequiresForBuildRequiresPackageIDTest(unittest.TestCase):

    def test(self):
        client = TestClient()
        save(client.cache.new_config_path, "core.package_id:default_python_mode=full_version_mode")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=tool --version=1.1.1")

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                python_requires ="tool/[>=0.0]"
            """)

        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": conanfile,
                     "myprofile": "[tool_requires]\ntool/[>=0.0]\n"})

        client2.run("create . --name=pkg --version=0.1 -pr=myprofile")
        self.assertIn("tool/1.1.1", client2.out)
        self.assertIn(f"pkg/0.1: Package '{PKG_ID_1}' created",
                      client2.out)

        client.run("create . --name=tool --version=1.1.2")
        client2.run("install --requires=pkg/0.1@ -pr=myprofile", assert_error=True)
        self.assertIn(f"ERROR: Missing binary: pkg/0.1:{PKG_ID_2}",
                      client2.out)
        self.assertIn("tool/1.1.2", client2.out)
        self.assertNotIn("tool/1.1.1", client2.out)

        client2.run("create . --name=pkg --version=0.1 -pr=myprofile")
        # self.assertIn("pkg/0.1: Applying build-requirement: tool/1.1.2", client2.out)
        self.assertIn(f"pkg/0.1: Package '{PKG_ID_2}' created",
                      client2.out)


class TestPythonRequiresHeaderOnly:
    def test_header_only(self):
        c = TestClient(light=True)
        pkg = textwrap.dedent("""\
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                python_requires = "tool/[*]"
                def package_id(self):
                    self.info.clear()
                """)
        c.save({"tool/conanfile.py": GenConanfile("tool"),
                "pkg/conanfile.py": pkg})
        c.run("create tool --version=1.0")
        c.run("create pkg")
        pkgid = c.created_package_id("pkg/0.1")
        c.run("create tool --version=1.2")
        c.run("install --requires=pkg/0.1")
        c.assert_listed_binary({"pkg/0.1": (pkgid, "Cache")})

    def test_header_only_implements(self):
        c = TestClient(light=True)
        pkg = textwrap.dedent("""\
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                python_requires = "tool/[*]"
                package_type = "header-library"
                implements = ["auto_header_only"]
                """)
        c.save({"tool/conanfile.py": GenConanfile("tool"),
                "pkg/conanfile.py": pkg})
        c.run("create tool --version=1.0")
        c.run("create pkg")
        pkgid = c.created_package_id("pkg/0.1")
        c.run("create tool --version=1.2")
        c.run("install --requires=pkg/0.1")
        c.assert_listed_binary({"pkg/0.1": (pkgid, "Cache")})
