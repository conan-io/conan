import unittest
from collections import OrderedDict

import time
import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, \
    inc_package_manifest_timestamp, inc_recipe_manifest_timestamp
from conans.util.env_reader import get_env


class RemoteChecksTest(unittest.TestCase):

    @pytest.mark.skipif(get_env("TESTING_REVISIONS_ENABLED", False), reason="No sense with revs")
    def test_recipe_updates(self):
        servers = OrderedDict()
        servers["server1"] = TestServer()
        servers["server2"] = TestServer()
        servers["server3"] = TestServer()

        client = TestClient(servers=servers, users={"server1": [("lasote", "mypass")],
                                                    "server2": [("lasote", "mypass")],
                                                    "server3": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
from conans.tools import load
class Pkg(ConanFile):
    exports_sources = "*.data"
    def package(self):
        self.copy("*")
    def package_info(self):
        self.output.info("%s")
        self.output.info("DATA: {}".format(load("data.data")))
"""

        for server in (1, 2, 3):
            server_name = "Server%s!" % server
            client.save({"conanfile.py": conanfile % server_name,
                         "data.data": "MyData%s" % server})
            client.run("create . Pkg/0.1@lasote/testing")
            inc_recipe_manifest_timestamp(client.cache, "Pkg/0.1@lasote/testing", (server - 1) * 20)
            inc_package_manifest_timestamp(client.cache,
                                           "Pkg/0.1@lasote/testing:%s" % NO_SETTINGS_PACKAGE_ID,
                                           (server-1) * 20)
            client.run("upload Pkg* -r=server%s --confirm --all" % server)

        # Fresh install from server1
        client.run("remove * -f")
        client.run("install Pkg/0.1@lasote/testing -r=server1")
        self.assertIn("Pkg/0.1@lasote/testing: Server1!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: DATA: MyData1", client.out)
        self.assertIn("Pkg/0.1@lasote/testing from 'server1' - Downloaded", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:%s - Download" % NO_SETTINGS_PACKAGE_ID, client.out)

        # install without updates
        client.run("install Pkg/0.1@lasote/testing -r=server2")
        self.assertIn("Pkg/0.1@lasote/testing from 'server1' - Cache", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:%s - Cache" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Server1!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: DATA: MyData1", client.out)

        # Update from server2
        client.run("install Pkg/0.1@lasote/testing -r=server2 --update")
        self.assertIn("Pkg/0.1@lasote/testing from 'server2' - Updated", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:%s - Update" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package %s"
                      " from remote 'server2' " % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Server2!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: DATA: MyData2", client.out)
        client.run("remote list_ref")
        self.assertIn("Pkg/0.1@lasote/testing: server2", client.out)

        # Update from server3
        client.run("install Pkg/0.1@lasote/testing -r=server3 --update")
        self.assertIn("Pkg/0.1@lasote/testing from 'server3' - Updated", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:%s - Update" % NO_SETTINGS_PACKAGE_ID,
                      client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package "
                      "%s from remote 'server3' " % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Server3!", client.out)
        client.run("remote list_ref")
        self.assertIn("Pkg/0.1@lasote/testing: server3", client.out)

    def test_multiple_remotes_single_upload(self):
        servers = OrderedDict([("server1", TestServer()),
                               ("server2", TestServer())])
        client = TestClient(servers=servers, users={"server1": [("lasote", "mypass")],
                                                    "server2": [("lasote", "mypass")]})
        conanfile = GenConanfile().with_setting("build_type")
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing -s build_type=Release")
        client.run("create . Pkg2/0.1@lasote/testing -s build_type=Release")
        client.run("remote add_ref Pkg/0.1@lasote/testing server1")
        client.run("remote add_ref Pkg2/0.1@lasote/testing server2")
        client.run("upload Pkg* --all --confirm")
        self.assertIn("Uploading Pkg/0.1@lasote/testing to remote 'server1'", client.out)
        self.assertIn("Uploading Pkg2/0.1@lasote/testing to remote 'server2'", client.out)

    def test_binary_packages_mixed(self):
        servers = OrderedDict([("server1", TestServer()),
                               ("server2", TestServer()),
                               ("server3", TestServer())])
        client = TestClient(servers=servers, users={"server1": [("lasote", "mypass")],
                                                    "server2": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "build_type"
    """
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing -s build_type=Release")
        client.run("upload Pkg* --all -r=server1 --confirm")

        # Built type Debug only in server2
        client.run('remove -f "*"')
        client.run("create . Pkg/0.1@lasote/testing -s build_type=Debug")
        client.run("upload Pkg* --all -r=server2 --confirm")

        # Remove all, install a package for debug
        client.run('remove -f "*"')
        # If revision it is able to fetch the binary from server2
        client.run('install Pkg/0.1@lasote/testing -s build_type=Debug',
                   assert_error=not client.cache.config.revisions_enabled)
        # Force binary from server2
        client.run('install Pkg/0.1@lasote/testing -s build_type=Debug -r server2')

        # Check registry, recipe should have been found from server1 and binary from server2
        ref = "Pkg/0.1@lasote/testing"
        pref = "%s:5a67a79dbc25fd0fa149a0eb7a20715189a0d988" % ref
        client.run("remote list_ref")
        self.assertIn("%s: server1" % ref, client.out)

        client.run("remote list_pref Pkg/0.1@lasote/testing")
        self.assertIn("%s: server2" % pref, client.out)
        # Use another client to update the server2 binary and server1 recipe
        client2 = TestClient(servers=servers, users={"server1": [("lasote", "mypass")],
                                                     "server2": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile, tools
class Pkg(ConanFile):
    settings = "build_type"

    def package(self):
        tools.save("myfile.lib", "fake")
    """
        client2.save({"conanfile.py": conanfile})
        time.sleep(1)
        client2.run("create . Pkg/0.1@lasote/testing -s build_type=Debug")
        client2.run("upload Pkg/0.1@lasote/testing --all")
        self.assertIn("Uploading Pkg/0.1@lasote/testing to remote 'server1'", client2.out)
        # The upload is not done to server2 because in client2 we don't have the registry
        # with the entry
        self.assertIn("Uploading package 1/1: "
                      "5a67a79dbc25fd0fa149a0eb7a20715189a0d988 to 'server1'", client2.out)

        ref2 = "Pkg/0.1@lasote/testing"
        pref2 = "%s:5a67a79dbc25fd0fa149a0eb7a20715189a0d988" % ref
        # Now the reference is associated with server1
        client2.run("remote list_ref")
        self.assertIn("%s: server1" % ref2, client2.out)

        client2.run("remote list_pref Pkg/0.1@lasote/testing")
        self.assertIn("%s: server1" % pref2, client2.out)

        # Force upload to server2
        client2.run("upload Pkg/0.1@lasote/testing --all -r server2")
        # An upload doesn't modify a registry, so still server1
        client2.run("remote list_ref")
        self.assertIn("%s: server1" % ref2, client2.out)

        client2.run("remote list_pref Pkg/0.1@lasote/testing")
        self.assertIn("%s: server1" % pref2, client2.out)

        # Now go back to client and update, confirm that recipe=> server1, package=> server2
        client.run("remote list_ref")
        self.assertIn("%s: server1" % ref, client.out)
        client.run("remote list_pref Pkg/0.1@lasote/testing")
        self.assertIn("%s: server2" % pref, client.out)

        # install --update will install a new recipe revision from server1
        # and the binary from server2
        client.run('install Pkg/0.1@lasote/testing -s build_type=Debug --update')
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving from remote 'server1'...", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package "
                      "5a67a79dbc25fd0fa149a0eb7a20715189a0d988 from remote 'server2' ", client.out)

        # Export new recipe, it should be non associated
        conanfile = """from conans import ConanFile, tools
class Pkg(ConanFile):
    settings = "build_type"

    def package(self):
        tools.save("myfile.lib", "fake2")
    """
        client2.save({"conanfile.py": conanfile})
        time.sleep(1)
        client.run("create . Pkg/0.1@lasote/testing -s build_type=Debug")
        client.run("remote list_ref")
        # FIXME: Conan 2.0 the package should be cleared from the registry after a create
        self.assertIn("Pkg/0.1@lasote/testing", client.out)

    def test_binary_defines_remote(self):
        servers = OrderedDict([("server1", TestServer()),
                               ("server2", TestServer()),
                               ("server3", TestServer())])
        client = TestClient(servers=servers, users={"server1": [("lasote", "mypass")],
                                                    "server2": [("lasote", "mypass")],
                                                    "server3": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing")
        client.run("upload Pkg* --all -r=server1 --confirm")
        client.run("upload Pkg* --all -r=server2 --confirm")

        # It takes the default remote
        client.run("remove * -f")
        client.run("remote list_ref")
        self.assertNotIn("Pkg", client.out)

        # Exported recipe gets binary from default remote
        client.run("export . Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing from local cache - Cache", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:%s - Download" % NO_SETTINGS_PACKAGE_ID,
                      client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package "
                      "%s from remote 'server1'" % NO_SETTINGS_PACKAGE_ID, client.out)
        client.run("remote list_ref")

        # The recipe is not downloaded from anywhere, it should be kept to local cache
        self.assertNotIn("Pkg/0.1@lasote/testing", client.out)

        # Explicit remote also defines the remote
        client.run("remove * -f")
        client.run("remote list_ref")
        self.assertNotIn("Pkg", client.out)
        client.run("export . Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing -r=server2")
        self.assertIn("Pkg/0.1@lasote/testing from local cache - Cache", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:%s - Download" % NO_SETTINGS_PACKAGE_ID,
                      client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package "
                      "%s from remote 'server2'" % NO_SETTINGS_PACKAGE_ID, client.out)
        client.run("remote list_ref")
        # Still not downloaded from anywhere, it shouldn't have a registry entry
        self.assertNotIn("Pkg/0.1@lasote/testing", client.out)

        # Ordered search of binary works
        client.run("remove * -f")
        client.run("remove * -f -r=server1")
        client.run("export . Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing from local cache - Cache", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:%s - Download" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package "
                      "%s from remote 'server2'" % NO_SETTINGS_PACKAGE_ID, client.out)
        client.run("remote list_ref")
        self.assertNotIn("Pkg/0.1@lasote/testing", client.out)

        # Download recipe and binary from the remote2 by iterating
        client.run("remove * -f")
        client.run("remove * -f -r=server1")
        client.run("install Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing from 'server2' - Downloaded", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:%s - Download" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package "
                      "%s from remote 'server2'" % NO_SETTINGS_PACKAGE_ID, client.out)
        client.run("remote list_ref")
        self.assertIn("Pkg/0.1@lasote/testing: server2", client.out)

    def test_binaries_from_different_remotes(self):
        servers = OrderedDict()
        servers["server1"] = TestServer()
        servers["server2"] = TestServer()
        client = TestClient(servers=servers, users={"server1": [("lasote", "mypass")],
                                                    "server2": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    options = {"opt": [1, 2, 3]}
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing -o Pkg:opt=1")
        client.run("upload Pkg* --all -r=server1 --confirm")
        client.run("remove * -p -f")
        client.run("create . Pkg/0.1@lasote/testing -o Pkg:opt=2")
        client.run("upload Pkg* --all -r=server2 --confirm")
        client.run("remove * -p -f")
        client.run("remote list_ref")

        # It keeps associated to server1 even after a create FIXME: Conan 2.0
        self.assertIn("Pkg/0.1@lasote/testing: server1", client.out)

        # Trying to install from another remote fails
        client.run("install Pkg/0.1@lasote/testing -o Pkg:opt=2 -r=server2")
        self.assertIn("Pkg/0.1@lasote/testing from 'server1' - Cache", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:b0c3b52601b7e36532a74a37c81bb432898a951b - Download", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package b0c3b52601b7e36532a74a37c81bb432898a951b "
                      "from remote 'server2'", client.out)

        # Nothing to update
        client.run("install Pkg/0.1@lasote/testing -o Pkg:opt=2 -r=server2 -u")
        self.assertIn("Pkg/0.1@lasote/testing from 'server2' - Cache", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:b0c3b52601b7e36532a74a37c81bb432898a951b - Cache",
                      client.out)

        # Build missing
        client.run("install Pkg/0.1@lasote/testing -o Pkg:opt=3 -r=server2", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'Pkg/0.1@lasote/testing'", client.out)

        client.run("install Pkg/0.1@lasote/testing -o Pkg:opt=3", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'Pkg/0.1@lasote/testing'", client.out)
