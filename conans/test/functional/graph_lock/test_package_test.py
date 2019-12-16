import textwrap
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class GraphLockTestPackageTest(unittest.TestCase):
    def augment_test_package_requires(self):
        # https://github.com/conan-io/conan/issues/6067
        # At this moment, it is not possible to add new nodes to a locked graph, which means
        # test_package with build_requires raise errors
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
        lock = client.load("conan.lock")
        client.run("create . -pr=profile --lockfile --build missing", assert_error=True)
        self.assertIn("ERROR: The node ID 5 was not found in the lock", client.out)
        # This would be the expected succesful output
        # self.assertIn("tool/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        # self.assertIn("dep/0.1: Applying build-requirement: tool/0.1", client.out)
        # self.assertIn("dep/0.1 (test package): Running test()", client.out)
