import textwrap
import unittest

from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import save


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
        self.client2.assert_listed_binary({"pkg/0.1": ("eda9a39e318258650fd92c53c544261297e11514",
                                                       "Build")})

        self.client.run("export . --name=tool --version=1.1.2")
        self.client2.run("create . --name=pkg --version=0.1")
        self.assertIn("tool/1.1.2", self.client2.out)
        self.client2.assert_listed_binary({"pkg/0.1": ("eda9a39e318258650fd92c53c544261297e11514",
                                                       "Build")})

        # With a minor change, it fires a rebuild
        self.client.run("export . --name=tool --version=1.2.0")
        self.client2.run("create . --name=pkg --version=0.1")
        self.assertIn("tool/1.2.0", self.client2.out)
        self.client2.assert_listed_binary({"pkg/0.1": ("cc0b4f4392034760802175c1b51bfaabc1d743d2",
                                                       "Build")})

    def test_change_mode_conf(self):
        # change the policy in conan.conf
        save(self.client2.cache.new_config_path, "core.package_id:default_python_mode=patch_mode")
        self.client2.run("create . --name=pkg --version=0.1")
        self.assertIn("tool/1.1.1", self.client2.out)
        self.client2.assert_listed_binary({"pkg/0.1": ("4001d4ba359a3f3d6583a134d38a3462fe936733",
                                                       "Build")})

        # with a patch change, new ID
        self.client.run("export . --name=tool --version=1.1.2")
        self.client2.run("create . --name=pkg --version=0.1")
        self.assertIn("tool/1.1.2", self.client2.out)
        self.client2.assert_listed_binary({"pkg/0.1": ("0fdcb8439123abfc619b4221353d9fabb87d8fba",
                                                       "Build")})

    def test_unrelated_conf(self):
        # change the policy in conan.conf
        self.client2.run("config set general.default_python_requires_id_mode=unrelated_mode")
        self.client2.run("create . pkg/0.1@")
        self.assertIn("tool/1.1.1", self.client2.out)
        self.assertIn("pkg/0.1:c941ae50e2daf4a118c393591cfef6a55cd1cfad - Build", self.client2.out)

        # with any change the package id doesn't change
        self.client.run("export . tool/1.1.2@")
        self.client2.run("create . pkg/0.1@ --build missing")
        self.assertIn("tool/1.1.2", self.client2.out)
        self.assertIn("pkg/0.1:c941ae50e2daf4a118c393591cfef6a55cd1cfad - Cache", self.client2.out)

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
        self.client2.assert_listed_binary({"pkg/0.1": ("4001d4ba359a3f3d6583a134d38a3462fe936733",
                                                       "Build")})

        # with a patch change, new ID
        self.client.run("export . --name=tool --version=1.1.2")
        self.client2.run("create . --name=pkg --version=0.1")
        self.assertIn("tool/1.1.2", self.client2.out)
        self.client2.assert_listed_binary({"pkg/0.1": ("0fdcb8439123abfc619b4221353d9fabb87d8fba",
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
        self.assertIn("pkg/0.1: Package '4001d4ba359a3f3d6583a134d38a3462fe936733' created",
                      client2.out)

        client.run("create . --name=tool --version=1.1.2")
        client2.run("install --requires=pkg/0.1@ -pr=myprofile", assert_error=True)
        self.assertIn("ERROR: Missing binary: pkg/0.1:0fdcb8439123abfc619b4221353d9fabb87d8fba",
                      client2.out)
        self.assertIn("tool/1.1.2", client2.out)
        self.assertNotIn("tool/1.1.1", client2.out)

        client2.run("create . --name=pkg --version=0.1 -pr=myprofile")
        # self.assertIn("pkg/0.1: Applying build-requirement: tool/1.1.2", client2.out)
        self.assertIn("pkg/0.1: Package '0fdcb8439123abfc619b4221353d9fabb87d8fba' created",
                      client2.out)
