import unittest

from parameterized import parameterized

from conans.test.utils.tools import TestServer, TestClient
from conans.model.ref import ConanFileReference, PackageReference
import os
import time
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from nose.plugins.attrib import attr
from conans.test.utils.test_files import uncompress_packaged_files


@attr("slow")
class CompleteFlowTest(unittest.TestCase):

    @parameterized.expand([(True, ), (False, )])
    def reuse_test(self, complete_urls):
        test_server = TestServer(complete_urls=complete_urls)
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

        conan_reference = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1", need_patch=True)
        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.client.run("install %s --build missing" % str(conan_reference))

        self.assertIn("Hello0/0.1@lasote/stable package(): Copied 1 '.h' file: helloHello0.h",
                      self.client.user_io.out)
        # Check compilation ok
        package_ids = self.client.paths.conan_packages(conan_reference)
        self.assertEquals(len(package_ids), 1)
        package_ref = PackageReference(conan_reference, package_ids[0])
        self._assert_library_exists(package_ref, self.client.paths)

        # Upload conans
        self.client.run("upload %s" % str(conan_reference))
        self.assertIn("Compressing recipe", str(self.client.user_io.out))

        # Not needed to tgz again
        self.client.run("upload %s" % str(conan_reference))
        self.assertNotIn("Compressing exported", str(self.client.user_io.out))

        # Check that conans exists on server
        server_paths = self.servers["default"].paths
        conan_path = server_paths.export(conan_reference)
        self.assertTrue(os.path.exists(conan_path))

        # Upload package
        self.client.run("upload %s -p %s" % (str(conan_reference), str(package_ids[0])))
        self.assertIn("Compressing package", str(self.client.user_io.out))

        # Not needed to tgz again
        self.client.run("upload %s -p %s" % (str(conan_reference), str(package_ids[0])))
        self.assertNotIn("Compressing package", str(self.client.user_io.out))

        # If we install the package again will be removed and re tgz
        self.client.run("install %s --build missing" % str(conan_reference))
        # Upload package
        self.client.run("upload %s -p %s" % (str(conan_reference), str(package_ids[0])))
        self.assertNotIn("Compressing package", str(self.client.user_io.out))

        # Check library on server
        self._assert_library_exists_in_server(package_ref, server_paths)

        # Now from other "computer" install the uploaded conans with same options (nothing)
        other_conan = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        other_conan.run("install %s --build missing" % str(conan_reference))
        # Build should be empty
        build_path = other_conan.paths.build(package_ref)
        self.assertFalse(os.path.exists(build_path))
        # Lib should exist
        self._assert_library_exists(package_ref, other_conan.paths)

        # Now install it but with other options
        other_conan.run('install %s -o language=1 --build missing' % (str(conan_reference)))
        # Should have two packages
        package_ids = other_conan.paths.conan_packages(conan_reference)
        self.assertEquals(len(package_ids), 2)
        for package_id in package_ids:
            ref = PackageReference(conan_reference, package_id)
            self._assert_library_exists(ref, other_conan.paths)

        client3 = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        files3 = cpp_hello_conan_files("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        client3.save(files3)
        client3.run('install .')
        client3.run('build .')
        command = os.sep.join([".", "bin", "say_hello"])
        client3.runner(command, cwd=client3.current_folder)
        self.assertIn("Hello Hello1", client3.user_io.out)
        self.assertIn("Hello Hello0", client3.user_io.out)

        client3.run('install . -o language=1 --build missing')
        time.sleep(1)
        client3.run('build .')

        command = os.sep.join([".", "bin", "say_hello"])
        client3.runner(command, cwd=client3.current_folder)
        self.assertIn("Hola Hello1", client3.user_io.out)
        self.assertIn("Hola Hello0", client3.user_io.out)

    def _assert_library_exists(self, package_ref, paths):
        package_path = paths.package(package_ref)
        self.assertTrue(os.path.exists(os.path.join(package_path, "lib")))
        self._assert_library_files(package_path)

    def _assert_library_files(self, path):
        libraries = os.listdir(os.path.join(path, "lib"))
        self.assertEquals(len(libraries), 1)

    def _assert_library_exists_in_server(self, package_ref, paths):
        folder = uncompress_packaged_files(paths, package_ref)
        self._assert_library_files(folder)
