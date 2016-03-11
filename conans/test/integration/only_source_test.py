import unittest
from conans.test.tools import TestServer, TestClient
from conans.model.ref import ConanFileReference
import os
from conans.paths import CONANFILE
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import load


class OnlySourceTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer([("*/*@*/*", "*")],  # read permissions
                                 [],  # write permissions
                                 users={"lasote": "mypass"})  # exported users and passwords
        self.servers = {"default": test_server}

    def _create(self, client, number, version, deps=None, export=True):
        files = cpp_hello_conan_files(number, version, deps)
        # To avoid building
        files = {CONANFILE: files[CONANFILE].replace("build(", "build2(").replace("config(",
                                                                                  "config2(")}
        client.save(files, clean_first=True)
        if export:
            client.run("export lasote/stable")

    def conan_test_test(self):
        '''Checks --build in test command'''

        client = TestClient(servers=self.servers, users={"default":[("lasote", "mypass")]})
        self._create(client, "Hello0", "0.0")
        self._create(client, "Hello1", "1.1", ["Hello0/0.0@lasote/stable"])

        # Now test out Hello2
        self._create(client, "Hello2", "2.2", ["Hello1/1.1@lasote/stable"], export=True)
        hello2conanfile = load(os.path.join(client.current_folder, CONANFILE))
        hello2conanfile = hello2conanfile.replace("(ConanFile):",
                                                  "(ConanFile):\n    myname='pepe'\n")
        client.save({CONANFILE: hello2conanfile})

        test_conanfile = '''
from conans.model.conan_file import ConanFile

class DefaultNameConan(ConanFile):
    name = "DefaultName"
    version = "0.1"
    settings = "os", "compiler", "arch"
    requires = "Hello2/2.2@lasote/stable"
    generators = "cmake"

    def test(self):
        pass
        '''
        client.save({"test/%s" % CONANFILE: test_conanfile})

        # Should recognize the hello package
        # Will Fail because Hello0/0.0 and Hello1/1.1 has not built packages
        # and by default no packages are built
        error = client.run("test", ignore_error=True)
        self.assertTrue(error)
        self.assertIn('Try to build from sources with "--build Hello0"', client.user_io.out)

        # We generate the package for Hello0/0.0
        client.run("install Hello0/0.0@lasote/stable --build Hello0")

        # Still missing Hello1/1.1
        error = client.run("test", ignore_error=True)
        self.assertTrue(error)
        self.assertIn('Try to build from sources with "--build Hello1"', client.user_io.out)

        # We generate the package for Hello1/1.1
        client.run("install Hello1/1.1@lasote/stable --build Hello1")

        # Now Hello2 should be built and not fail
        client.run("test")
        self.assertNotIn("Can't find a 'Hello2/2.2@lasote/stable' package", client.user_io.out)
        self.assertIn('Hello2/2.2@lasote/stable: WARN: Forced build from source',
                      client.user_io.out)

        # Now package is generated but should be built again
        client.run("test")
        self.assertIn('Hello2/2.2@lasote/stable: WARN: Forced build from source',
                      client.user_io.out)

        # Now if name is not detected in conanfile
        client.save({CONANFILE: ""})
        client.run("test")
        self.assertIn('Cannot detect a valid conanfile in current directory', client.user_io.out)
        # It found the package already generated
        self.assertIn('Hello2/2.2@lasote/stable: Already installed!', client.user_io.out)

    def reuse_test(self):

        client = TestClient(servers=self.servers, users={"default":[("lasote", "mypass")]})
        conan_reference = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1")
        files[CONANFILE] = files[CONANFILE].replace("build", "build2")

        client.save(files)
        client.run("export lasote/stable")
        client.run("install %s --build missing" % str(conan_reference))

        self.assertTrue(os.path.exists(client.paths.builds(conan_reference)))
        self.assertTrue(os.path.exists(client.paths.packages(conan_reference)))

        # Upload
        client.run("upload %s --all" % str(conan_reference))

        # Now from other "computer" install the uploaded conans with same options (nothing)
        other_conan = TestClient(servers=self.servers, users={"default":[("lasote", "mypass")]})
        other_conan.run("install %s --build missing" % str(conan_reference))
        self.assertFalse(os.path.exists(other_conan.paths.builds(conan_reference)))
        self.assertTrue(os.path.exists(other_conan.paths.packages(conan_reference)))

        # Now from other "computer" install the uploaded conans with same options (nothing)
        other_conan = TestClient(servers=self.servers, users={"default":[("lasote", "mypass")]})
        other_conan.run("install %s --build" % str(conan_reference))
        self.assertTrue(os.path.exists(other_conan.paths.builds(conan_reference)))
        self.assertTrue(os.path.exists(other_conan.paths.packages(conan_reference)))

        # Use an invalid pattern and check that its not builded from source
        other_conan = TestClient(servers=self.servers, users={"default":[("lasote", "mypass")]})
        other_conan.run("install %s --build HelloInvalid" % str(conan_reference))
        self.assertFalse(os.path.exists(other_conan.paths.builds(conan_reference)))
        self.assertTrue(os.path.exists(other_conan.paths.packages(conan_reference)))

        # Use another valid pattern and check that its not builded from source
        other_conan = TestClient(servers=self.servers, users={"default":[("lasote", "mypass")]})
        other_conan.run("install %s --build HelloInvalid -b Hello" % str(conan_reference))
        self.assertTrue(os.path.exists(other_conan.paths.builds(conan_reference)))
        self.assertTrue(os.path.exists(other_conan.paths.packages(conan_reference)))

        # Now even if the package is in local store, check that's rebuilded
        other_conan.run("install %s -b Hello*" % str(conan_reference))
        self.assertIn("Copying sources to build folder", other_conan.user_io.out)

        other_conan.run("install %s" % str(conan_reference))
        self.assertNotIn("Copying sources to build folder", other_conan.user_io.out)
