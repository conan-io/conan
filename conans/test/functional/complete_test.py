import os
import time
import unittest

import pytest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.test_files import uncompress_packaged_files
from conans.test.utils.tools import TestClient, TestServer


@pytest.mark.slow
@pytest.mark.tool_cmake
class CompleteFlowTest(unittest.TestCase):

    def test_reuse_complete_urls(self):
        # This test can be removed in conan 2.0 when the complete_urls is removed
        test_server = TestServer(complete_urls=True)
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        client.save(files)
        client.run("create . lasote/stable")
        self.assertIn("Hello0/0.1@lasote/stable package(): Packaged 1 '.h' file: helloHello0.h",
                      client.out)

        # Upload package
        client.run("upload %s --all" % str(ref))
        self.assertIn("Compressing package", client.out)

        # Not needed to tgz again
        client.run("upload %s --all" % str(ref))
        self.assertNotIn("Compressing package", client.out)

        # Now from other "computer" install the uploaded packages with same options
        other_conan = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        other_conan.run("install %s" % str(ref))

        # Now install it but with other options
        other_conan.run('install %s -o language=1 --build missing' % (str(ref)))
        # Should have two packages
        package_ids = other_conan.cache.package_layout(ref).package_ids()
        self.assertEqual(len(package_ids), 2)

    def test_reuse(self):
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1", need_patch=True)
        client.save(files)
        client.run("create . lasote/stable")
        self.assertIn("Hello0/0.1@lasote/stable package(): Packaged 1 '.h' file: helloHello0.h",
                      client.out)
        # Check compilation ok
        package_ids = client.cache.package_layout(ref).package_ids()
        self.assertEqual(len(package_ids), 1)
        pref = PackageReference(ref, package_ids[0])
        self._assert_library_exists(pref, client.cache)

        # Upload package
        client.run("upload %s" % str(ref))
        self.assertIn("Compressing recipe", client.out)

        # Not needed to tgz again
        client.run("upload %s" % str(ref))
        self.assertNotIn("Compressing exported", client.out)

        # Check that recipe exists on server
        server_paths = servers["default"].server_store
        rev = server_paths.get_last_revision(ref).revision
        conan_path = server_paths.export(ref.copy_with_rev(rev))
        self.assertTrue(os.path.exists(conan_path))

        # Upload package
        client.run("upload %s -p %s" % (str(ref), str(package_ids[0])))
        self.assertIn("Compressing package", client.out)

        # Not needed to tgz again
        client.run("upload %s -p %s" % (str(ref), str(package_ids[0])))
        self.assertNotIn("Compressing package", client.out)

        # If we install the package again will be removed and re tgz
        client.run("install %s" % str(ref))
        # Upload package
        client.run("upload %s -p %s" % (str(ref), str(package_ids[0])))
        self.assertNotIn("Compressing package", client.out)

        # Check library on server
        self._assert_library_exists_in_server(pref, server_paths)

        # Now from other "computer" install the uploaded conans with same options (nothing)
        other_conan = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        other_conan.run("install %s" % str(ref))
        # Build should be empty
        build_path = other_conan.cache.package_layout(pref.ref).build(pref)
        self.assertFalse(os.path.exists(build_path))
        # Lib should exist
        self._assert_library_exists(pref, other_conan.cache)

        # Now install it but with other options
        other_conan.run('install %s -o language=1 --build missing' % (str(ref)))
        # Should have two packages
        package_ids = other_conan.cache.package_layout(ref).package_ids()
        self.assertEqual(len(package_ids), 2)
        for package_id in package_ids:
            pref = PackageReference(ref, package_id)
            self._assert_library_exists(pref, other_conan.cache)

        client3 = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        files3 = cpp_hello_conan_files("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        client3.save(files3)
        client3.run('install .')
        client3.run('build .')
        command = os.sep.join([".", "bin", "say_hello"])
        client3.run_command(command)
        self.assertIn("Hello Hello1", client3.out)
        self.assertIn("Hello Hello0", client3.out)

        client3.run('install . -o language=1 --build missing')
        time.sleep(1)
        client3.run('build .')

        command = os.sep.join([".", "bin", "say_hello"])
        client3.run_command(command)
        self.assertIn("Hola Hello1", client3.out)
        self.assertIn("Hola Hello0", client3.out)

    def _assert_library_exists(self, pref, paths):
        package_path = paths.package_layout(pref.ref).package(pref)
        self.assertTrue(os.path.exists(os.path.join(package_path, "lib")))
        self._assert_library_files(package_path)

    def _assert_library_files(self, path):
        libraries = os.listdir(os.path.join(path, "lib"))
        self.assertEqual(len(libraries), 1)

    def _assert_library_exists_in_server(self, pref, paths):
        folder = uncompress_packaged_files(paths, pref)
        self._assert_library_files(folder)
