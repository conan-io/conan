import textwrap
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class CompatibleIDsTest(unittest.TestCase):

    def compatible_test(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CompatiblePackage

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    if self.settings.compiler == "gcc" and self.settings.compiler.version == "4.9":
                        for version in ("4.8", "4.7", "4.6"):
                            compatible_pkg = CompatiblePackage(self)
                            compatible_pkg.settings.compiler.version = version
                            self.compatible_packages.append(compatible_pkg)
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=4.9
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile -s compiler.version=4.8")
        self.assertIn("pkg/0.1@user/stable: Package '22c594d7fed4994c59a1eacb24ff6ff48bc5c51c'"
                      " created", client.out)

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable:22c594d7fed4994c59a1eacb24ff6ff48bc5c51c", client.out)
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

    def error_setting_test(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CompatiblePackage

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    compatible_pkg = CompatiblePackage(self)
                    compatible_pkg.settings.compiler.version = "bad"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/0.1@user/stable",  assert_error=True)

        self.assertIn('ERROR: pkg/0.1@user/stable: Error in package_id() method, line 8',
                      client.out)
        self.assertIn('compatible_pkg.settings.compiler.version = "bad"', client.out)
        self.assertIn("ConanException: Invalid setting 'bad' is not a valid "
                      "'settings.compiler.version' value", client.out)

