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
        client.run("upload Pkg* --all --confirm -r default")
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
        package_id_release = re.search(r"Pkg/0.1@lasote/testing:(\S+)", str(client.out)).group(1)
        the_time = time.time()
        with patch.object(RevisionList, '_now', return_value=the_time):
            client.run("upload Pkg* --all -r=server1 --confirm")

        # Built type Debug only in server2
        client.run('remove -f "*"')
        client.run("create . Pkg/0.1@lasote/testing -s build_type=Debug")
        package_id_debug = re.search(r"Pkg/0.1@lasote/testing:(\S+)", str(client.out)).group(1)
        # the revision in server2 will have a date that's older
        the_time = the_time - 10
        with patch.object(RevisionList, '_now', return_value=the_time):
            client.run("upload Pkg* --all -r=server2 --confirm")

        # Remove all, install a package for debug
        client.run('remove -f "*"')
        # If revision it is able to fetch the binary from server2
        client.run('install Pkg/0.1@lasote/testing -s build_type=Debug')
        # Force binary from server2
        client.run('install Pkg/0.1@lasote/testing -s build_type=Debug -r server2')

        # Check registry, we will have the recipe from server1 because it had a newer date
        # as we did not specify remote when installing conan checked all the latest revisions
        # for each server and took the latest
        ref = "Pkg/0.1@lasote/testing"
        rrev = "1b25ee13ed28ed6349426f272e44a1da"
        pref = f"%s#1b25ee13ed28ed6349426f272e44a1da:{package_id_debug}#2c2736de567a6e278851c9eebfd26fdb" % ref
        client.run("remote list_ref")
        self.assertIn(f"{ref}#{rrev}: server1", client.out)

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
        client2.run("create . Pkg/0.1@lasote/testing -s build_type=Debug")
        the_time = time.time()
        with patch.object(RevisionList, '_now', return_value=the_time):
            client2.run("upload Pkg/0.1@lasote/testing --all -r default")
        self.assertIn("Uploading Pkg/0.1@lasote/testing to remote 'server1'", client2.out)
        # The upload is not done to server2 because in client2 we don't have the registry
        # with the entry
        self.assertIn(f"Uploading package 1/1: {package_id_debug} to 'server1'", client2.out)

        ref2 = "Pkg/0.1@lasote/testing"
        rrev2 = "2f81612204de158d4448529e554ffdd6"
        pref2 = f"%s#2f81612204de158d4448529e554ffdd6:{package_id_debug}#2c2736de567a6e278851c9eebfd26fdb" % ref
        # Now the reference is associated with server1
        client2.run("remote list_ref")
        self.assertIn(f"{ref2}#{rrev2}: server1", client2.out)

        client2.run("remote list_pref Pkg/0.1@lasote/testing")
        self.assertIn("%s: server1" % pref2, client2.out)

        # Force upload to server2
        the_time = the_time + 100
        with patch.object(RevisionList, '_now', return_value=the_time):
            client2.run("upload Pkg/0.1@lasote/testing --all -r server2")
        # An upload doesn't modify a registry, so still server1
        client2.run("remote list_ref")
        self.assertIn(f"{ref2}#{rrev2}: server1", client2.out)

        client2.run("remote list_pref Pkg/0.1@lasote/testing")
        self.assertIn("%s: server1" % pref2, client2.out)

        # Now go back to client and update, confirm that recipe=> server1, package=> server2
        client.run("remote list_ref")
        self.assertIn(f"{ref}#{rrev}: server1", client.out)
        client.run("remote list_pref Pkg/0.1@lasote/testing")
        self.assertIn("%s: server2" % pref, client.out)

        # install --update will both recipe and binary from server2 (the latest)
        client.run('install Pkg/0.1@lasote/testing -s build_type=Debug --update')
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving from remote 'server2'...", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Retrieving package "
                      f"{package_id_debug} from remote 'server2' ", client.out)

        # Export new recipe, it should be non associated
        conanfile = """from conans import ConanFile, tools
class Pkg(ConanFile):
    settings = "build_type"

    def package(self):
        tools.save("myfile.lib", "fake2")
    """
        client2.save({"conanfile.py": conanfile})
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
        latest_rrev = client.cache.get_latest_rrev(
            ConanFileReference.loads("Pkg/0.1@lasote/testing"))
        self.assertIn(f"{latest_rrev.full_str()}: server2", client.out)

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
        client.run("remote list_ref")

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
