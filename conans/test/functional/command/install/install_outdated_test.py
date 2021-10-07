import time
import unittest
from collections import OrderedDict

import pytest

from conans.model.ref import ConanFileReference
from conans.test.assets.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient, TestServer, TurboTestClient, GenConanfile
from conans.util.env_reader import get_env
from conans.util.files import rmdir


class InstallOutdatedPackagesTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        self.new_client = TestClient(servers=self.servers,
                                     users={"default": [("lasote", "mypass")]})

        self.ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        self.client.save(files)
        self.client.run("export . lasote/stable")

        self.client.run("install Hello0/0.1@lasote/stable --build missing")
        self.client.run("upload  Hello0/0.1@lasote/stable --all")

    @pytest.mark.skipif(get_env("TESTING_REVISIONS_ENABLED", False), reason="No sense with revs")
    def test_install_outdated(self):
        # If we try to install the same package with --build oudated it's already ok
        self.client.run("install Hello0/0.1@lasote/stable --build outdated")
        self.assertIn("Hello0/0.1@lasote/stable: Package is up to date", self.client.out)

        # Then we can export a modified recipe and try to install without --build outdated
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        files["conanfile.py"] += "\n#Otherline"
        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.client.run("install Hello0/0.1@lasote/stable")
        self.assertIn("Hello0/0.1@lasote/stable: Already installed!", self.client.out)
        self.assertNotIn("Package is up to date", self.client.out)
        self.assertNotIn("Outdated package!", self.client.out)

        # Try now with the --build outdated
        self.client.run("install Hello0/0.1@lasote/stable --build outdated")
        self.assertNotIn("Package is up to date", self.client.out)
        self.assertIn("Outdated package!", self.client.out)
        self.assertIn("Building your package", self.client.out)

        # Remove all local references, export again (the modified version not uploaded)
        # and try to install, it will discard the remote package too
        self.client.run("remove Hello0* -f")
        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.client.run("remote add_ref Hello0/0.1@lasote/stable default")
        self.client.run("install Hello0/0.1@lasote/stable --build outdated")
        self.assertNotIn("Hello0/0.1@lasote/stable: Already installed!", self.client.out)
        self.assertNotIn("Package is up to date", self.client.out)
        self.assertIn("Building your package", self.client.out)

    def test_install_outdated_dep(self):
        # A new recipe that depends on Hello0/0.1
        new_client = TestClient(servers=self.servers,
                                users={"default": [("lasote", "mypass")]})
        files = cpp_hello_conan_files("Hello1", "0.1", ["Hello0/0.1@lasote/stable"], build=False)
        new_client.save(files)
        new_client.run("export . lasote/stable")
        self.assertIn("A new conanfile.py version was exported", new_client.out)
        # It will retrieve from the remote Hello0 and build Hello1
        new_client.run("install Hello1/0.1@lasote/stable --build missing")

        # Then modify REMOTE Hello0 recipe files (WITH THE OTHER CLIENT)
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        files["conanfile.py"] += "\n#MODIFIED RECIPE"
        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.assertIn("A new conanfile.py version was exported", self.client.out)
        self.client.run("install Hello0/0.1@lasote/stable --build missing")
        # Upload only the recipe, so the package is outdated in the server
        self.client.run("upload Hello0/0.1@lasote/stable")

        # Now, with the new_client, remove only the binary package from Hello0
        rmdir(new_client.cache.package_layout(self.ref).packages())
        # And try to install Hello1 again, should not complain because the remote
        # binary is in the "same version" than local cached Hello0
        new_client.run("install Hello1/0.1@lasote/stable --build outdated")
        self.assertIn("Downloading conan_package.tgz", new_client.out)
        self.assertIn("Hello0/0.1@lasote/stable: Package is up to date", new_client.out)

        # With revisions makes no sense, it won't download an outdated package, it belongs to
        # a different recipe
        if not new_client.cache.config.revisions_enabled:
            # But if we remove the full Hello0 local package, will retrieve the updated
            # recipe and the outdated package
            new_client.run("remove Hello0* -f")
            new_client.run("install Hello1/0.1@lasote/stable --build outdated")
            self.assertIn("Hello0/0.1@lasote/stable: Outdated package!", new_client.out)
            self.assertIn("Hello0/0.1@lasote/stable: Building your package", new_client.out)

    def test_install_outdated_and_dep(self):
        # regression test for https://github.com/conan-io/conan/issues/1053
        # A new recipe that depends on Hello0/0.1
        new_client = TestClient(servers=self.servers,
                                users={"default": [("lasote", "mypass")]})
        files = cpp_hello_conan_files("Hello1", "0.1", ["Hello0/0.1@lasote/stable"], build=False)
        new_client.save(files)
        new_client.run("export . lasote/stable")
        self.assertIn("A new conanfile.py version was exported", new_client.out)
        # It will retrieve from the remote Hello0 and build Hello1
        new_client.run("install Hello1/0.1@lasote/stable --build missing")

        # Then modify REMOTE Hello0 recipe files (WITH THE OTHER CLIENT)
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        files["conanfile.py"] += "\n#MODIFIED RECIPE"
        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.assertIn("A new conanfile.py version was exported", self.client.out)
        self.client.run("install Hello0/0.1@lasote/stable --build missing")
        # Upload only the recipe, so the package is outdated in the server
        self.client.run("upload Hello0/0.1@lasote/stable")

        # Now, with the new_client, remove only the binary package from Hello0
        rmdir(new_client.cache.package_layout(self.ref).packages())
        # And try to install Hello1 again, should not complain because the remote
        # binary is in the "same version" than local cached Hello0
        new_client.run("install Hello1/0.1@lasote/stable --build outdated --build Hello1")
        self.assertIn("Downloading conan_package.tgz", new_client.out)
        self.assertIn("Hello1/0.1@lasote/stable: Forced build from source",
                      new_client.out)

    def test_install_outdated_checking_updates(self):
        server = TestServer()
        servers = OrderedDict([("default", server)])
        client = TurboTestClient(servers=servers)
        client2 = TurboTestClient(servers=servers)

        ref = ConanFileReference.loads("lib/1.0@conan/testing")
        client.create(ref)
        client.upload_all(ref)

        # Generate a new recipe, the binary becomes outdated
        time.sleep(1)
        client2.create(ref, conanfile=GenConanfile().with_build_msg("Some modified stuff"))
        client2.run("upload {} -r default".format(ref))

        # Update, building the outdated
        client.run("install -u -b outdated {}".format(ref))
        # The outdated is built
        self.assertIn("Some modified stuff", client.out)
