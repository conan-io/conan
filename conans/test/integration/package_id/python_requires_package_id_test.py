import textwrap
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class PythonRequiresPackageIDTest(unittest.TestCase):

    def setUp(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . tool/1.1.1@")
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                python_requires ="tool/[*]"
            """)
        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": conanfile})
        self.client = client
        self.client2 = client2

    def test_default(self):
        self.client2.run("create . pkg/0.1@")
        self.assertEqual(1, str(self.client2.out).count(" resolved to 'tool/1.1.1' in local cache"))
        self.assertIn("tool/1.1.1", self.client2.out)
        self.assertIn("pkg/0.1:ecc024bdf63d1355af81d60281c569492d98901c - Build", self.client2.out)

        self.client.run("export . tool/1.1.2@")
        self.client2.run("create . pkg/0.1@")
        self.assertIn("tool/1.1.2", self.client2.out)
        self.assertIn("pkg/0.1:ecc024bdf63d1355af81d60281c569492d98901c - Build", self.client2.out)

        # With a minor change, it fires a rebuild
        self.client.run("export . tool/1.2.0@")
        self.client2.run("create . pkg/0.1@")
        self.assertIn("tool/1.2.0", self.client2.out)
        self.assertIn("pkg/0.1:2f471d7bec8ea131369a4b683cd1aeea65a18861 - Build", self.client2.out)

    def test_change_mode_conf(self):
        # change the policy in conan.conf
        self.client2.run("config set general.default_python_requires_id_mode=patch_mode")
        self.client2.run("create . pkg/0.1@")
        self.assertIn("tool/1.1.1", self.client2.out)
        self.assertIn("pkg/0.1:f3161fafc8273fe3c8afa3b51dcc198c33f66033 - Build", self.client2.out)

        # with a patch change, new ID
        self.client.run("export . tool/1.1.2@")
        self.client2.run("create . pkg/0.1@")
        self.assertIn("tool/1.1.2", self.client2.out)
        self.assertIn("pkg/0.1:387c1c797a011d426ecb25a1e01b28251e443ec8 - Build", self.client2.out)

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
            from conans import ConanFile
            class Pkg(ConanFile):
                python_requires ="tool/[*]"
                def package_id(self):
                    self.info.python_requires.patch_mode()
            """)
        self.client2.save({"conanfile.py": conanfile})
        self.client2.run("create . pkg/0.1@")
        self.assertIn("tool/1.1.1", self.client2.out)
        self.assertIn("pkg/0.1:f3161fafc8273fe3c8afa3b51dcc198c33f66033 - Build", self.client2.out)

        # with a patch change, new ID
        self.client.run("export . tool/1.1.2@")
        self.client2.run("create . pkg/0.1@")
        self.assertIn("tool/1.1.2", self.client2.out)
        self.assertIn("pkg/0.1:387c1c797a011d426ecb25a1e01b28251e443ec8 - Build", self.client2.out)


class PythonRequiresForBuildRequiresPackageIDTest(unittest.TestCase):

    def test(self):
        client = TestClient()
        client.run("config set general.default_python_requires_id_mode=full_version_mode")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . tool/1.1.1@")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                python_requires ="tool/[>=0.0]"
            """)

        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": conanfile,
                     "myprofile": "[build_requires]\ntool/[>=0.0]\n"})

        client2.run("create . pkg/0.1@ -pr=myprofile")
        self.assertIn("tool/1.1.1", client2.out)
        self.assertIn("pkg/0.1: Package 'f3161fafc8273fe3c8afa3b51dcc198c33f66033' created",
                      client2.out)

        client.run("create . tool/1.1.2@")
        client2.run("install pkg/0.1@ -pr=myprofile", assert_error=True)
        self.assertIn("ERROR: Missing binary: pkg/0.1:387c1c797a011d426ecb25a1e01b28251e443ec8",
                      client2.out)
        self.assertIn("tool/1.1.2", client2.out)
        self.assertNotIn("tool/1.1.1", client2.out)

        client2.run("create . pkg/0.1@ -pr=myprofile")
        self.assertIn("pkg/0.1: Applying build-requirement: tool/1.1.2", client2.out)
        self.assertIn("pkg/0.1: Package '387c1c797a011d426ecb25a1e01b28251e443ec8' created",
                      client2.out)
