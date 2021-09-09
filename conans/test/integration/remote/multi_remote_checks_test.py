import re
import unittest
from collections import OrderedDict

import time
from mock import patch

from conans.model.ref import ConanFileReference
from conans.server.revision_list import RevisionList
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer


class RemoteChecksTest(unittest.TestCase):

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

        # Exported recipe gets binary from default remote
        client.run("export . Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing from local cache - Cache", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:%s - Download" % NO_SETTINGS_PACKAGE_ID,
                      client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package "
                      "%s from remote 'server1'" % NO_SETTINGS_PACKAGE_ID, client.out)

        # Explicit remote also defines the remote
        client.run("remove * -f")
        client.run("export . Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing -r=server2")
        self.assertIn("Pkg/0.1@lasote/testing from local cache - Cache", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:%s - Download" % NO_SETTINGS_PACKAGE_ID,
                      client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package "
                      "%s from remote 'server2'" % NO_SETTINGS_PACKAGE_ID, client.out)

        # Ordered search of binary works
        client.run("remove * -f")
        client.run("remove * -f -r=server1")
        client.run("export . Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing from local cache - Cache", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:%s - Download" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package "
                      "%s from remote 'server2'" % NO_SETTINGS_PACKAGE_ID, client.out)

        # Download recipe and binary from the remote2 by iterating
        client.run("remove * -f")
        client.run("remove * -f -r=server1")
        client.run("install Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing from 'server2' - Downloaded", client.out)
        self.assertIn("Pkg/0.1@lasote/testing:%s - Download" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package "
                      "%s from remote 'server2'" % NO_SETTINGS_PACKAGE_ID, client.out)

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
        package_id2 = re.search(r"Pkg/0.1@lasote/testing:(\S+)", str(client.out)).group(1)
        client.run("upload Pkg* --all -r=server2 --confirm")
        client.run("remove * -p -f")

        # It keeps associated to server1 even after a create FIXME: Conan 2.0
        latest_rrev = client.cache.get_latest_rrev(ConanFileReference.loads("Pkg/0.1@lasote/testing"))
        self.assertIn(f"{latest_rrev.full_str()}: server1", client.out)

        # Trying to install from another remote fails
        client.run("install Pkg/0.1@lasote/testing -o Pkg:opt=2 -r=server2")
        self.assertIn("Pkg/0.1@lasote/testing from 'server1' - Cache", client.out)
        self.assertIn(f"Pkg/0.1@lasote/testing:{package_id2} - Download", client.out)
        self.assertIn(f"Pkg/0.1@lasote/testing: Retrieving package {package_id2} "
                      "from remote 'server2'", client.out)

        # Nothing to update
        client.run("install Pkg/0.1@lasote/testing -o Pkg:opt=2 -r=server2 -u")
        self.assertIn("Pkg/0.1@lasote/testing from 'server2' - Cache", client.out)
        self.assertIn(f"Pkg/0.1@lasote/testing:{package_id2} - Cache",
                      client.out)

        # Build missing
        client.run("install Pkg/0.1@lasote/testing -o Pkg:opt=3 -r=server2", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'Pkg/0.1@lasote/testing'", client.out)

        client.run("install Pkg/0.1@lasote/testing -o Pkg:opt=3", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'Pkg/0.1@lasote/testing'", client.out)
