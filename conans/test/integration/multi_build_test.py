import unittest
from conans.test.utils.tools import TestClient
from conans.model.ref import ConanFileReference
import os
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from nose.plugins.attrib import attr


@attr("slow")
class CollectLibsTest(unittest.TestCase):

    def collect_libs_test(self):
        conan_reference = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1", collect_libs=True)
        client = TestClient()
        client.save(files)
        client.run("export lasote/stable")

        client.run("install %s --build missing" % str(conan_reference))

        # Check compilation ok
        package_ids = client.paths.conan_packages(conan_reference)
        self.assertEquals(len(package_ids), 1)

        # Reuse them
        conan_reference = ConanFileReference.loads("Hello1/0.2@lasote/stable")
        files3 = cpp_hello_conan_files("Hello1", "0.1", ["Hello0/0.1@lasote/stable"],
                                       collect_libs=True)

        # reusing the binary already in cache
        client.save(files3, clean_first=True)
        client.run('install')
        client.run('build')

        command = os.sep.join([".", "bin", "say_hello"])
        client.runner(command, cwd=client.current_folder)
        self.assertIn("Hello Hello1", client.user_io.out)
        self.assertIn("Hello Hello0", client.user_io.out)

        # rebuilding the binary in cache
        client.run('remove "*" -p -f')
        client.run('install --build')
        client.run('build')

        command = os.sep.join([".", "bin", "say_hello"])
        client.runner(command, cwd=client.current_folder)
        self.assertIn("Hello Hello1", client.user_io.out)
        self.assertIn("Hello Hello0", client.user_io.out)
