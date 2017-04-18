import unittest
from conans.test.utils.tools import TestClient, TestServer
import os
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import CONANFILE
from conans.model.ref import ConanFileReference, PackageReference
from conans.util.files import load


class InstallSelectedPackagesTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        self.package_ids = self._upload_some_packages(self.client)
        self.new_client = TestClient(servers=self.servers,
                                     users={"default": [("lasote", "mypass")]})

    def install_all_test(self):
        # Should retrieve the three packages
        self.new_client.run("install Hello0/0.1@lasote/stable --all")
        p1 = os.path.join(self.new_client.paths.packages(self.ref))
        packages = os.listdir(p1)
        self.assertEquals(len(packages), 3)

    def install_some_reference_test(self):
        # Should retrieve the specified packages
        self.new_client.run("install Hello0/0.1@lasote/stable -p %s" % self.package_ids[0])
        packages = os.listdir(self.new_client.paths.packages(self.ref))
        self.assertEquals(len(packages), 1)
        self.assertEquals(packages[0], self.package_ids[0])

        self.new_client.run("install Hello0/0.1@lasote/stable -p %s -p %s" % (self.package_ids[0],
                                                                              self.package_ids[1]))
        packages = os.listdir(self.new_client.paths.packages(self.ref))
        self.assertEquals(len(packages), 2)

    def download_recipe_twice_test(self):
        expected_conanfile_contents = self.files[CONANFILE]
        self.new_client.run("install Hello0/0.1@lasote/stable --all")
        got_conanfile = load(os.path.join(self.new_client.paths.export(self.ref), CONANFILE))
        self.assertEquals(expected_conanfile_contents, got_conanfile)

        self.new_client.run("install Hello0/0.1@lasote/stable --all")
        got_conanfile = load(os.path.join(self.new_client.paths.export(self.ref), CONANFILE))
        self.assertEquals(expected_conanfile_contents, got_conanfile)

        self.new_client.run("install Hello0/0.1@lasote/stable --all")
        got_conanfile = load(os.path.join(self.new_client.paths.export(self.ref), CONANFILE))
        self.assertEquals(expected_conanfile_contents, got_conanfile)

    def download_packages_twice_test(self):
        expected_header_contents = self.files["helloHello0.h"]
        package_folder = self.new_client.paths.package(PackageReference(self.ref, self.package_ids[0]))

        self.new_client.run("install Hello0/0.1@lasote/stable --all")
        got_header = load(os.path.join(package_folder, "include", "helloHello0.h"))
        self.assertEquals(expected_header_contents, got_header)

        self.new_client.run("install Hello0/0.1@lasote/stable --all")
        got_header = load(os.path.join(package_folder, "include", "helloHello0.h"))
        self.assertEquals(expected_header_contents, got_header)

        self.new_client.run("install Hello0/0.1@lasote/stable --all")
        got_header = load(os.path.join(package_folder, "include", "helloHello0.h"))
        self.assertEquals(expected_header_contents, got_header)

    def install_all_but_no_packages_test(self):

        # Remove all from remote
        self.new_client.run("remove Hello* -f -r default")

        # Try to install all
        self.new_client.run("install Hello0/0.1@lasote/stable --all", ignore_error=True)
        self.assertIn("'Hello0/0.1@lasote/stable' not found in remote", self.new_client.user_io.out)

        # Upload only the recipe
        self.new_client.save(self.files)
        self.new_client.run("export lasote/stable")
        self.new_client.run("upload  Hello0/0.1@lasote/stable --all")

        # And try to download all
        self.new_client.run("install Hello0/0.1@lasote/stable --all")
        self.assertIn("No remote binary packages found in remote", self.new_client.user_io.out)

    def _upload_some_packages(self, client):
        self.ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        self.files = cpp_hello_conan_files("Hello0", "0.1")
        # No build.
        self.files[CONANFILE] = self.files[CONANFILE].replace("def build(self):", "def build(self):\n        return\n")
        client.save(self.files)
        client.run("export lasote/stable")
        client.run("install Hello0/0.1@lasote/stable -s os=Windows --build missing")
        client.run("install Hello0/0.1@lasote/stable -s os=Linux --build missing")
        client.run("install Hello0/0.1@lasote/stable -s os=Linux -s compiler=gcc -s "
                   "compiler.version=4.6 -s compiler.libcxx=libstdc++ --build missing")
        client.run("upload  Hello0/0.1@lasote/stable --all")
        return os.listdir(self.client.paths.packages(self.ref))
