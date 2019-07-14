import os
import unittest

from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load


class OnlySourceTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}

    def _create(self, client, number, version, deps=None, export=True):
        files = cpp_hello_conan_files(number, version, deps, build=False, config=False)

        client.save(files, clean_first=True)
        if export:
            client.run("export . lasote/stable")

    def conan_test_test(self):
        '''Checks --build in test command'''

        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        self._create(client, "Hello0", "0.0")
        self._create(client, "Hello1", "1.1", ["Hello0/0.0@lasote/stable"])

        # Now test out Hello2
        self._create(client, "Hello2", "2.2", ["Hello1/1.1@lasote/stable"], export=True)
        hello2conanfile = load(os.path.join(client.current_folder, CONANFILE))
        client.save({CONANFILE: hello2conanfile})

        test_conanfile = '''
from conans.model.conan_file import ConanFile

class DefaultNameConan(ConanFile):
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
        client.run("create . lasote/stable", assert_error=True)
        self.assertIn('Try to build it from sources with "--build Hello0"', client.out)

        # We generate the package for Hello0/0.0
        client.run("install Hello0/0.0@lasote/stable --build Hello0")

        # Still missing Hello1/1.1
        client.run("create . lasote/stable", assert_error=True)
        self.assertIn('Try to build it from sources with "--build Hello1"', client.out)

        # We generate the package for Hello1/1.1
        client.run("install Hello1/1.1@lasote/stable --build Hello1")

        # Now Hello2 should be built and not fail
        client.run("create . lasote/stable")
        self.assertNotIn("Can't find a 'Hello2/2.2@lasote/stable' package", client.out)
        self.assertIn('Hello2/2.2@lasote/stable: Forced build from source',
                      client.out)

        # Now package is generated but should be built again
        client.run("create . lasote/stable")
        self.assertIn('Hello2/2.2@lasote/stable: Forced build from source',
                      client.out)

    def build_policies_update_test(self):
        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        conanfile = """
from conans import ConanFile

class MyPackage(ConanFile):
    name = "test"
    version = "1.9"
    build_policy = 'always'

    def source(self):
        self.output.info("Getting sources")
    def build(self):
        self.output.info("Building sources")
    def package(self):
        self.output.info("Packaging this test package")
        """

        files = {CONANFILE: conanfile}
        client.save(files, clean_first=True)
        client.run("export . lasote/stable")
        client.run("install test/1.9@lasote/stable")
        self.assertIn("Getting sources", client.out)
        self.assertIn("Building sources", client.out)
        self.assertIn("Packaging this test package", client.out)
        self.assertIn("Building package from source as defined by build_policy='always'",
                      client.out)
        client.run("upload test/1.9@lasote/stable")

    def build_policies_in_conanfile_test(self):

        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        files = cpp_hello_conan_files("Hello0", "1.0", [], config=False, build=False)

        #  --- Build policy to missing ---
        files[CONANFILE] = files[CONANFILE].replace("exports = '*'",
                                                    "exports = '*'\n    build_policy = 'missing'")
        client.save(files, clean_first=True)
        client.run("export . lasote/stable")

        # Install, it will build automatically if missing (without the --build missing option)
        client.run("install Hello0/1.0@lasote/stable")
        self.assertIn("Building", client.out)
        self.assertNotIn("Generator txt created conanbuildinfo.txt", client.out)

        # Try to do it again, now we have the package, so no build is done
        client.run("install Hello0/1.0@lasote/stable")
        self.assertNotIn("Building", client.out)
        self.assertNotIn("Generator txt created conanbuildinfo.txt", client.out)

        # Try now to upload all packages, should not crash because of the "missing" build policy
        client.run("upload Hello0/1.0@lasote/stable --all")

        #  --- Build policy to always ---
        files[CONANFILE] = files[CONANFILE].replace("build_policy = 'missing'",
                                                    "build_policy = 'always'")
        client.save(files, clean_first=True)
        client.run("export . lasote/stable")

        # Install, it will build automatically if missing (without the --build missing option)
        client.run("install Hello0/1.0@lasote/stable")
        self.assertIn("Detected build_policy 'always', trying to remove source folder",
                      client.out)
        self.assertIn("Building", client.out)
        self.assertNotIn("Generator txt created conanbuildinfo.txt", client.out)

        # Try to do it again, now we have the package, but we build again
        client.run("install Hello0/1.0@lasote/stable")
        self.assertIn("Building", client.out)
        self.assertIn("Detected build_policy 'always', trying to remove source folder",
                      client.out)
        self.assertNotIn("Generator txt created conanbuildinfo.txt", client.out)

        # Try now to upload all packages, should crash because of the "always" build policy
        client.run("upload Hello0/1.0@lasote/stable --all", assert_error=True)
        self.assertIn("no packages can be uploaded", client.out)

    def reuse_test(self):
        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1")
        files[CONANFILE] = files[CONANFILE].replace("build", "build2")

        client.save(files)
        client.run("export . lasote/stable")
        client.run("install %s --build missing" % str(ref))

        self.assertTrue(os.path.exists(client.cache.package_layout(ref).builds()))
        self.assertTrue(os.path.exists(client.cache.package_layout(ref).packages()))

        # Upload
        client.run("upload %s --all" % str(ref))

        # Now from other "computer" install the uploaded conans with same options (nothing)
        other_client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        other_client.run("install %s --build missing" % str(ref))
        self.assertFalse(os.path.exists(other_client.cache.package_layout(ref).builds()))
        self.assertTrue(os.path.exists(other_client.cache.package_layout(ref).packages()))

        # Now from other "computer" install the uploaded conans with same options (nothing)
        other_client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        other_client.run("install %s --build" % str(ref))
        self.assertTrue(os.path.exists(other_client.cache.package_layout(ref).builds()))
        self.assertTrue(os.path.exists(other_client.cache.package_layout(ref).packages()))

        # Use an invalid pattern and check that its not builded from source
        other_client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        other_client.run("install %s --build HelloInvalid" % str(ref))
        self.assertIn("No package matching 'HelloInvalid' pattern", other_client.out)
        self.assertFalse(os.path.exists(other_client.cache.package_layout(ref).builds()))
        # self.assertFalse(os.path.exists(other_client.cache.package_layout(ref).packages()))

        # Use another valid pattern and check that its not builded from source
        other_client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        other_client.run("install %s --build HelloInvalid -b Hello" % str(ref))
        self.assertIn("No package matching 'HelloInvalid' pattern", other_client.out)
        # self.assertFalse(os.path.exists(other_client.cache.package_layout(ref).builds()))
        # self.assertFalse(os.path.exists(other_client.cache.package_layout(ref).packages()))

        # Now even if the package is in local store, check that's rebuilded
        other_client.run("install %s -b Hello*" % str(ref))
        self.assertIn("Copying sources to build folder", other_client.out)

        other_client.run("install %s" % str(ref))
        self.assertNotIn("Copying sources to build folder", other_client.out)
