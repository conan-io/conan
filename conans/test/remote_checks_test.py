import unittest
from conans.test.utils.tools import TestClient, TestServer,\
    inc_recipe_manifest_timestamp, inc_package_manifest_timestamp
from collections import OrderedDict


class RemoteChecksTest(unittest.TestCase):

    def test_recipe_updates(self):
        servers = {"server1": TestServer(), "server2": TestServer(), "server3": TestServer()}
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
            inc_recipe_manifest_timestamp(client.client_cache, "Pkg/0.1@lasote/testing", (server-1)*20)
            inc_package_manifest_timestamp(client.client_cache,
                                           "Pkg/0.1@lasote/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                                           (server-1)*20)
            client.run("upload Pkg* -r=server%s --confirm --all" % server)

        # The remote defined is the first one that was used for upload
        client.run("remote list_ref")
        self.assertIn("Pkg/0.1@lasote/testing: server1", client.out)

        # Fresh install from server1
        client.run("remove * -f")
        client.run("install Pkg/0.1@lasote/testing -r=server1")
        self.assertIn("Pkg/0.1@lasote/testing: Server1!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: DATA: MyData1", client.out)
        self.assertIn("Pkg/0.1@lasote/testing from 'server1' - Downloaded", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Download", client.out)

        # install without updates
        client.run("install Pkg/0.1@lasote/testing -r=server2")
        self.assertIn("Pkg/0.1@lasote/testing from 'server1' - Cache", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Server1!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: DATA: MyData1", client.out)

        # Update from server2
        client.run("install Pkg/0.1@lasote/testing -r=server2 --update")
        self.assertIn("Pkg/0.1@lasote/testing from 'server2' - Updated", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Update", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
                      " from remote 'server2' ", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Server2!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: DATA: MyData2", client.out)
        client.run("remote list_ref")
        self.assertIn("Pkg/0.1@lasote/testing: server2", client.out)

        # Update from server3
        client.run("install Pkg/0.1@lasote/testing -r=server3 --update")
        self.assertIn("Pkg/0.1@lasote/testing from 'server3' - Updated", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Update", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
                      " from remote 'server3' ", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Server3!", client.out)
        client.run("remote list_ref")
        self.assertIn("Pkg/0.1@lasote/testing: server3", client.out)

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
        self.assertIn("Pkg/0.1@lasote/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Download", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 "
                      "from remote 'server1'", client.out)
        client.run("remote list_ref")
        self.assertIn("Pkg/0.1@lasote/testing: server1", client.out)

        # Explicit remote also defines the remote
        client.run("remove * -f")
        client.run("remote list_ref")
        self.assertNotIn("Pkg", client.out)
        client.run("export . Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing -r=server2")
        self.assertIn("Pkg/0.1@lasote/testing from local cache - Cache", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Download", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 "
                      "from remote 'server2'", client.out)
        client.run("remote list_ref")
        self.assertIn("Pkg/0.1@lasote/testing: server2", client.out)

        # Ordered search of binary works
        client.run("remove * -f")
        client.run("remove * -f -r=server1")
        client.run("export . Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing from local cache - Cache", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Download", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 "
                      "from remote 'server2'", client.out)
        client.run("remote list_ref")
        self.assertIn("Pkg/0.1@lasote/testing: server2", client.out)

    def test_binaries_from_different_remotes(self):
        servers = {"server1": TestServer(), "server2": TestServer(), "server3": TestServer()}
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
        self.assertIn("Pkg/0.1@lasote/testing:b0c3b52601b7e36532a74a37c81bb432898a951b - Cache", client.out)

        # Build missing
        error = client.run("install Pkg/0.1@lasote/testing -o Pkg:opt=3 -r=server2", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Missing prebuilt package for 'Pkg/0.1@lasote/testing'", client.out)

        error = client.run("install Pkg/0.1@lasote/testing -o Pkg:opt=3", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Missing prebuilt package for 'Pkg/0.1@lasote/testing'", client.out)
