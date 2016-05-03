import unittest
from conans.test.tools import TestServer, TestClient
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import hello_conan_files
import os
from conans.util.files import save
from conans.model.ref import PackageReference


class ManifestValidationTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer([("*/*@*/*", "*")],  # read permissions
                                 [],  # write permissions
                                 users={"lasote": "mypass"})  # exported users and passwords
        self.servers = {"default": test_server}
        self.conan = TestClient(servers=self.servers, users={"default":[("lasote", "mypass")]})

        # Export and upload the conanfile
        self.conan_reference = ConanFileReference.loads("hello0/0.1@lasote/stable")
        self.files = hello_conan_files(conan_reference=self.conan_reference, lang='go')
        self.conan.save(self.files, clean_first=True)
        self.conan.run("export lasote/stable")
        self.conan.run("upload %s" % str(self.conan_reference))

    def test_corrupted_conanfile(self):
        # If we try to install it it will find in local folder (no remote call)
        self.conan.run("install %s --build missing" % str(self.conan_reference))
        self.assertNotIn("Conan %s not found, retrieving from server" % str(self.conan_reference),
                         self.conan.user_io.out)

        # Now alter a local file and try to install it,
        # conan should download the conanfile from remote
        # because the local files are not correct

        export_path = self.conan.paths.export(self.conan_reference)
        file_path = os.path.join(export_path, list(self.files.keys())[0])
        save(file_path, "BAD CONTENT")

        self.conan.run("install %s --build missing" % str(self.conan_reference))
        self.assertIn("Bad conanfile detected!", str(self.conan.user_io.out))
        self.assertIn("%s: Retrieving from remote 'default'"
                      % str(self.conan_reference),
                      self.conan.user_io.out)

    def test_corrupted_package(self):
        # Install and generate a package
        self.conan.run("install %s --build missing" % str(self.conan_reference))
        package_ref = PackageReference(self.conan_reference,
                                       "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

        # If we make the install again it will find the already generated package
        self.conan.run("install %s --build missing" % str(self.conan_reference))
        self.assertNotIn("Package for %s does not exist" % str(self.conan_reference),
                         self.conan.user_io.out)
        self.assertIn("%s: Already installed!" % str(self.conan_reference), self.conan.user_io.out)

        # Now alter a local file and try to install it,
        # conan should try to download the package from remote
        # because the local files are not correct
        package_path = self.conan.paths.package(package_ref)
        file_path = os.path.join(package_path, "hello0/hello.go")
        save(file_path, "BAD CONTENT")

        self.conan.run("install %s --build missing" % str(self.conan_reference))
        self.assertIn("%s: WARN: Bad package" % str(self.conan_reference),
                      self.conan.user_io.out)
