import unittest
from conans.test.utils.tools import TestClient
import os
from conans.model.ref import PackageReference, ConanFileReference
from conans.util.files import load


base_conanfile = '''
from conans import ConanFile

class TestSystemReqs(ConanFile):
    name = "Test"
    version = "0.1"
    options = {"myopt": [True, False]}
    default_options = "myopt=True"

    def system_requirements(self):
        self.output.info("*+Running system requirements+*")
        %GLOBAL%
        return "Installed my stuff"
'''


class SystemReqsTest(unittest.TestCase):

    def local_system_requirements_test(self):
        client = TestClient()
        files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "")}
        client.save(files)
        client.run("install .")
        self.assertIn("*+Running system requirements+*", client.user_io.out)

        files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "self.run('fake command!')")}
        client.save(files)
        with self.assertRaisesRegexp(Exception, "Command failed"):
            client.run("install .")

    def per_package_test(self):
        client = TestClient()
        files = {'conanfile.py': base_conanfile.replace("%GLOBAL%", "")}
        client.save(files)
        client.run("export user/testing")
        client.run("install Test/0.1@user/testing --build missing")
        self.assertIn("*+Running system requirements+*", client.user_io.out)
        conan_ref = ConanFileReference.loads("Test/0.1@user/testing")
        self.assertFalse(os.path.exists(client.paths.system_reqs(conan_ref)))
        package_ref = PackageReference(conan_ref, "f0ba3ca2c218df4a877080ba99b65834b9413798")
        load_file = load(client.paths.system_reqs_package(package_ref))
        self.assertIn("Installed my stuff", load_file)

        # Run again
        client.run("install Test/0.1@user/testing --build missing")
        self.assertNotIn("*+Running system requirements+*", client.user_io.out)
        self.assertFalse(os.path.exists(client.paths.system_reqs(conan_ref)))
        load_file = load(client.paths.system_reqs_package(package_ref))
        self.assertIn("Installed my stuff", load_file)

        # Run with different option
        client.run("install Test/0.1@user/testing -o myopt=False --build missing")
        self.assertIn("*+Running system requirements+*", client.user_io.out)
        self.assertFalse(os.path.exists(client.paths.system_reqs(conan_ref)))
        package_ref2 = PackageReference(conan_ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        load_file = load(client.paths.system_reqs_package(package_ref2))
        self.assertIn("Installed my stuff", load_file)

        # remove packages
        client.run("remove Test* -f -p 544", ignore_error=True)
        self.assertTrue(os.path.exists(client.paths.system_reqs_package(package_ref)))
        client.run("remove Test* -f -p f0ba3ca2c218df4a877080ba99b65834b9413798")
        self.assertFalse(os.path.exists(client.paths.system_reqs_package(package_ref)))
        self.assertTrue(os.path.exists(client.paths.system_reqs_package(package_ref2)))
        client.run("remove Test* -f -p 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertFalse(os.path.exists(client.paths.system_reqs_package(package_ref)))
        self.assertFalse(os.path.exists(client.paths.system_reqs_package(package_ref2)))

    def global_test(self):
        client = TestClient()
        files = {'conanfile.py': base_conanfile.replace("%GLOBAL%",
                                                        "self.global_system_requirements=True")}
        client.save(files)
        client.run("export user/testing")
        client.run("install Test/0.1@user/testing --build missing")
        self.assertIn("*+Running system requirements+*", client.user_io.out)
        conan_ref = ConanFileReference.loads("Test/0.1@user/testing")
        package_ref = PackageReference(conan_ref, "a527106fd9f2e3738a55b02087c20c0a63afce9d")
        self.assertFalse(os.path.exists(client.paths.system_reqs_package(package_ref)))
        load_file = load(client.paths.system_reqs(conan_ref))
        self.assertIn("Installed my stuff", load_file)

        # Run again
        client.run("install Test/0.1@user/testing --build missing")
        self.assertNotIn("*+Running system requirements+*", client.user_io.out)
        self.assertFalse(os.path.exists(client.paths.system_reqs_package(package_ref)))
        load_file = load(client.paths.system_reqs(conan_ref))
        self.assertIn("Installed my stuff", load_file)

        # Run with different option
        client.run("install Test/0.1@user/testing -o myopt=False --build missing")
        self.assertNotIn("*+Running system requirements+*", client.user_io.out)
        package_ref2 = PackageReference(conan_ref, "54c9626b48cefa3b819e64316b49d3b1e1a78c26")
        self.assertFalse(os.path.exists(client.paths.system_reqs_package(package_ref)))
        self.assertFalse(os.path.exists(client.paths.system_reqs_package(package_ref2)))
        load_file = load(client.paths.system_reqs(conan_ref))
        self.assertIn("Installed my stuff", load_file)

        # remove packages
        client.run("remove Test* -f -p")
        self.assertFalse(os.path.exists(client.paths.system_reqs_package(package_ref)))
        self.assertFalse(os.path.exists(client.paths.system_reqs_package(package_ref2)))
        self.assertFalse(os.path.exists(client.paths.system_reqs(conan_ref)))

    def wrong_output_test(self):
        client = TestClient()
        files = {'conanfile.py':
                 base_conanfile.replace("%GLOBAL%", "").replace('"Installed my stuff"', 'None')}
        client.save(files)
        client.run("export user/testing")
        client.run("install Test/0.1@user/testing --build missing")
        self.assertIn("*+Running system requirements+*", client.user_io.out)
        conan_ref = ConanFileReference.loads("Test/0.1@user/testing")
        self.assertFalse(os.path.exists(client.paths.system_reqs(conan_ref)))
        package_ref = PackageReference(conan_ref, "f0ba3ca2c218df4a877080ba99b65834b9413798")
        load_file = load(client.paths.system_reqs_package(package_ref))
        self.assertEqual('', load_file)
