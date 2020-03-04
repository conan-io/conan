import textwrap
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class GraphLockTestPackageTest(unittest.TestCase):
    def augment_test_package_requires(self):
        # https://github.com/conan-io/conan/issues/6067
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("tool").with_version("0.1")})
        client.run("create .")

        conanfile = textwrap.dedent("""
            from conans import ConanFile 
            class BugTest(ConanFile):
                def test(self):
                    pass
            """)
        client.save({"conanfile.py": GenConanfile().with_name("dep").with_version("0.1"),
                     "test_package/conanfile.py": conanfile,
                     "consumer.txt": "[requires]\ndep/0.1\n",
                     "profile": "[build_requires]\ntool/0.1\n"})

        client.run("export .")
        client.run("graph lock consumer.txt -pr=profile --build missing")

        # Check lock
        client.run("create . -pr=profile --lockfile --build missing")
        self.assertIn("tool/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("dep/0.1: Applying build-requirement: tool/0.1", client.out)
        self.assertIn("dep/0.1 (test package): Running test()", client.out)

    def test_command_test(self):
        client = TestClient()
        test_conanfile = textwrap.dedent("""
            from conans import ConanFile
            class BugTest(ConanFile):
                def test(self):
                    pass
            """)
        dblex = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "os"
                def build_requirements(self):
                    if self.settings.os == "FreeBSD":
                        self.build_requires("breakpad/0.1")
            """)
        standard = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "os"
                requires = "dblex/0.1"
                def requirements(self):
                    if self.settings.os == "FreeBSD":
                        self.requires("breakpad/0.1")
            """)
        client.save({"breakpad/conanfile.py": GenConanfile(),
                     "breakpad/test_package/conanfile.py": test_conanfile,
                     "dblex/conanfile.py": dblex,
                     "standard/conanfile.py": standard})
        client.run("export breakpad breakpad/0.1@")
        client.run("export dblex dblex/0.1@")
        client.run("export standard standard/0.1@")

        client.run("graph lock standard --build -s os=FreeBSD")
        print(client.out)
        client.run("graph build-order . --build=outdated --build=cascade")
        client.run("create breakpad breakpad/0.1@ --lockfile --test-folder=None")
        client.run("test breakpad/test_package breakpad/0.1@ --lockfile")
