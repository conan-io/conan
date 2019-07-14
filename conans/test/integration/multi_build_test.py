import os
import unittest

from nose.plugins.attrib import attr

from conans.model.ref import ConanFileReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient


@attr("slow")
class CollectLibsTest(unittest.TestCase):

    def collect_libs_test(self):
        ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1", collect_libs=True)
        client = TestClient()
        client.save(files)
        client.run("export . lasote/stable")

        client.run("install %s --build missing" % str(ref))

        # Check compilation ok
        package_ids = client.cache.package_layout(ref).conan_packages()
        self.assertEqual(len(package_ids), 1)

        # Reuse them
        files3 = cpp_hello_conan_files("Hello1", "0.1", ["Hello0/0.1@lasote/stable"],
                                       collect_libs=True)

        # reusing the binary already in cache
        client.save(files3, clean_first=True)
        client.run('install .')
        client.run('build .')

        command = os.sep.join([".", "bin", "say_hello"])
        client.run_command(command)
        self.assertIn("Hello Hello1", client.out)
        self.assertIn("Hello Hello0", client.out)

        # rebuilding the binary in cache
        client.run('remove "*" -p -f')
        client.run('install . --build')
        client.run('build .')

        command = os.sep.join([".", "bin", "say_hello"])
        client.run_command(command)
        self.assertIn("Hello Hello1", client.out)
        self.assertIn("Hello Hello0", client.out)
