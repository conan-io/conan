import os
import unittest
from collections import OrderedDict

from conans import tools, API_V2, REVISIONS
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, TestServer, create_local_git_repo

@unittest.skipUnless(os.environ.get("CONAN_SERVER_REVISIONS", API_V2) == API_V2, "Test only apiv2")
class RevisionsTest(unittest.TestCase):

    conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    def build(self):
        self.output.warn("Revision 1")        
'''
    ref = ConanFileReference.loads("lib/1.0@lasote/testing")

    def setUp(self):
        self.servers = OrderedDict()
        self.users = {}
        for i in range(3):
            self.servers["remote%d" % i] = TestServer(server_capabilities=[API_V2, REVISIONS])
            self.users["remote%d" % i] = [("lasote", "mypass")]

        self.servers["remote_norevisions"] = TestServer(server_capabilities=[])
        self.users["remote_norevisions"] = [("lasote", "mypass")]
        self.client = TestClient(servers=self.servers, users=self.users)

    def _create_and_upload(self, conanfile, reference, remote=None, args=""):
        remote = remote or "remote0"
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . %s %s" % (str(reference), args))
        self.client.run("upload %s -c --all -r %s" % (str(reference), remote))

    def test_revisions_recipes_without_scm(self):

        self._create_and_upload(self.conanfile, self.ref)
        rev = self.servers["remote0"].paths.get_last_revision(self.ref)
        self.assertEquals(rev, "149570a812b46d87c7dfa6408809b370")

        # Create a new revision and upload
        conanfile = self.conanfile.replace("Revision 1", "Revision 2")
        self._create_and_upload(conanfile, self.ref)

        # Remove local and install latest
        self.client.run("remove %s -f" % str(self.ref))
        self.client.run("install %s --build" % str(self.ref))
        self.assertIn("Revision 2", self.client.out)

        # Remove local and install first
        self.client.run("remove %s -f" % str(self.ref))
        self.client.run("install %s#149570a812b46d87c7dfa6408809b370 --build" % str(self.ref))
        self.assertIn("Revision 1", self.client.out)

    def test_revisions_packages_download(self):
        conanfile = '''
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):
    
    def build(self):
        tools.save("myfile.txt", os.getenv("PACKAGE_CONTENTS"))
        
    def package(self):
        self.copy("*")
'''
        with tools.environment_append({"PACKAGE_CONTENTS": "1"}):
            self._create_and_upload(conanfile, self.ref)
        rev = self.servers["remote0"].paths.get_last_revision(self.ref)
        self.assertEquals(rev, "202f9ce41808083a0f0c0d071fb5f398")

        self.ref.revision = rev
        p_ref = PackageReference(self.ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        pkg_rev = self.servers["remote0"].paths.get_last_package_revision(p_ref)
        self.assertEquals(pkg_rev, "e18c97f441d104e8be42d1ad7e9d425d")

        # Create new package revision for the same recipe
        with tools.environment_append({"PACKAGE_CONTENTS": "2"}):
            self._create_and_upload(conanfile, self.ref.copy_without_revision())
        pkg_rev = self.servers["remote0"].paths.get_last_package_revision(p_ref)
        self.assertEquals(pkg_rev, "7200b02593a12d8cf214c92ddf805ea9")

        # Delete all from local
        self.client.run("remove %s -f" % str(self.ref.copy_without_revision()))

        # Download specifying recipe with revisions and package with revisions
        self.client.run("download %s -p 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#"
                        "7200b02593a12d8cf214c92ddf805ea9" % str(self.ref))

        contents = tools.load(os.path.join(self.client.paths.package(p_ref), "myfile.txt"))
        self.assertEquals(contents, "2")

        # Download previous package revision
        self.client.run("download %s -p 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#"
                        "e18c97f441d104e8be42d1ad7e9d425d" % str(self.ref))
        contents = tools.load(os.path.join(self.client.paths.package(p_ref), "myfile.txt"))
        self.assertEquals(contents, "1")

    def test_search_with_revision(self):
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    settings = "os"
    def build(self):
        self.output.warn("Revision 1")        
'''
        self._create_and_upload(conanfile, self.ref, args="-s os=Linux")
        rev1 = self.servers["remote0"].paths.get_last_revision(self.ref)
        self._create_and_upload(conanfile.replace('"os"', '"arch"'), self.ref, args="-s arch=x86")
        rev2 = self.servers["remote0"].paths.get_last_revision(self.ref)
        self.assertNotEqual(rev1, rev2)

        # Search every package in local cache (we get both binary packages)
        self.client.run("search lib/1.0@lasote/testing")
        self.assertIn("a363db07e8420d258dca5a64aad6a5b8ecbbdd66", self.client.out)
        self.assertIn("cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31", self.client.out)

        # Search only revision 1 in local cache
        self.client.run("search lib/1.0@lasote/testing#%s" % rev1)
        self.assertNotIn("a363db07e8420d258dca5a64aad6a5b8ecbbdd66", self.client.out)
        self.assertIn("cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31", self.client.out)

        # Search only revision 2 in local cache
        self.client.run("search lib/1.0@lasote/testing#%s" % rev2)
        self.assertIn("a363db07e8420d258dca5a64aad6a5b8ecbbdd66", self.client.out)
        self.assertNotIn("cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31", self.client.out)

        # Search all in remote (will give us the latest)
        self.client.run("search lib/1.0@lasote/testing -r remote0")
        self.assertIn("a363db07e8420d258dca5a64aad6a5b8ecbbdd66", self.client.out)
        self.assertNotIn("cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31", self.client.out)

        # Search rev1 in remote
        self.client.run("search lib/1.0@lasote/testing#%s -r remote0" % rev1)
        self.assertNotIn("a363db07e8420d258dca5a64aad6a5b8ecbbdd66", self.client.out)
        self.assertIn("cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31", self.client.out)

        # Search rev2 in remote
        self.client.run("search lib/1.0@lasote/testing#%s -r remote0" % rev2)
        self.assertIn("a363db07e8420d258dca5a64aad6a5b8ecbbdd66", self.client.out)
        self.assertNotIn("cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31", self.client.out)

    def test_with_scm(self):
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    scm = {
        "revision": "auto",
        "url": "auto",
        "type": "git"
    }
    def build(self):
        self.output.warn("Revision 1")        
'''
        path, commit = create_local_git_repo({"myfile": "contents",
                                              "conanfile.py": conanfile}, branch="my_release")
        self.client.runner('git remote add origin https://myrepo.com.git', cwd=path)

        git = tools.Git(path)
        commit = git.get_commit()
        self.client.current_folder = path
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev_server = self.servers["remote0"].paths.get_last_revision(self.ref)
        self.assertEqual(commit, rev_server)

        self.client.run("remove %s -f" % str(self.ref))
        self.client.run("install %s#%s" % (str(self.ref), rev_server))
        self.assertIn("Package installed 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", self.client.out)

        self.client.run("remove %s -f" % str(self.ref))
        self.client.run("install %s" % str(self.ref))
        self.assertIn("Package installed 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", self.client.out)

    def test_upload_change_local_registry_with_revision(self):
        # An old recipe doesn't have revision in the registry, then we upload it to a server with
        # revisions, it should update the local registry with the revision
        self.client.save({"conanfile.py": self.conanfile})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s --all -c -r remote_norevisions" % str(self.ref))
        new_ref = self.client.remote_registry.get_ref_with_revision(self.ref)
        self.assertIsNone(new_ref.revision)
        self.assertEqual(new_ref, self.ref)

        self.client.run("upload %s --all -c -r remote0" % str(self.ref))
        new_ref = self.client.remote_registry.get_ref_with_revision(self.ref)
        self.assertIsNotNone(new_ref.revision)
        self.assertNotEqual(new_ref, self.ref)

    def test_upload_revision_and_upload_norevision(self):
        # A recipe versioned in a remote is uploaded to a remote without revisions
        self.client.save({"conanfile.py": self.conanfile})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s --all -c -r remote0" % str(self.ref))
        new_ref = self.client.remote_registry.get_ref_with_revision(self.ref)
        self.assertIsNotNone(new_ref.revision)
        self.assertNotEqual(new_ref, self.ref)

        self.client.run("upload %s --all -c -r remote_norevisions" % str(self.ref))
        new_ref = self.client.remote_registry.get_ref_with_revision(self.ref)
        self.assertIsNone(new_ref.revision)
        self.assertEqual(new_ref, self.ref)

    def test_info(self):
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    settings = "os"
    def build(self):
        self.output.warn("Revision 1")        
'''
        self._create_and_upload(conanfile, self.ref, args="-s os=Linux")
        self.client.run("info %s" % str(self.ref))
        self.assertIn("Revision: c5485544fd84cf85e45cc742feb8b34c", self.client.out)

        self._create_and_upload(conanfile, self.ref, args="-s os=Linux", remote="remote_norevisions")
        self.client.run("info %s" % str(self.ref))
        self.assertNotIn("Revision: c5485544fd84cf85e45cc742feb8b34c", self.client.out)

    def test_update_recipe(self):
        self.client.save({"conanfile.py": self.conanfile})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))

        client2 = TestClient(servers=self.servers, users=self.users)
        conanfile2 = self.conanfile + " "
        client2.save({"conanfile.py": conanfile2})
        client2.run("create . %s" % str(self.ref))
        client2.run("upload %s -c --all -r remote0" % str(self.ref))

        # install of the client1 (no-update)
        self.client.run("install %s" % str(self.ref))
        self.assertIn("lib/1.0@lasote/testing from 'remote0' - Cache", self.client.out)
        self.assertIn("lib/1.0@lasote/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                      self.client.out)

        # install with update
        self.client.run("install %s --update" % str(self.ref))
        self.assertIn("The current binary package doesn't belong to the current recipe revision:",
                      self.client.out)
        self.assertIn("lib/1.0@lasote/testing from 'remote0' - Updated", self.client.out)
        self.assertIn("lib/1.0@lasote/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Download",
                      self.client.out)

    def test_update_package(self):
        conanfile = '''
import time
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):
    def package(self):
        tools.save(os.path.join(self.package_folder, "file.txt"), str(time.time()))
'''

        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))

        # Same recipe, but will generate different package
        client2 = TestClient(servers=self.servers, users=self.users)
        client2.save({"conanfile.py": conanfile})
        client2.run("create . %s" % str(self.ref))
        client2.run("upload %s -c --all -r remote0" % str(self.ref))

        # install of the client1 (no-update)
        self.client.run("install %s" % str(self.ref))
        self.assertIn("lib/1.0@lasote/testing from 'remote0' - Cache", self.client.out)
        self.assertIn("lib/1.0@lasote/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                      self.client.out)

        # install with update
        self.client.run("install %s --update" % str(self.ref))
        self.assertNotIn("The current binary package doesn't belong to the current recipe revision:",
                         self.client.out)
        self.assertIn("Current package is older than remote upstream one", self.client.out)
        self.assertIn("lib/1.0@lasote/testing from 'remote0' - Cache", self.client.out)
        self.assertIn("lib/1.0@lasote/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Update",
                      self.client.out)

    def test_upload_outdated_packages(self):
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    settings = "os"      
'''
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . %s -s os=Windows" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))

        conanfile2 = self.conanfile + " "
        self.client.save({"conanfile.py": conanfile2})
        self.client.run("create . %s -s os=Linux" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        self.assertIn("Skipping package '3475bd55b91ae904ac96fde0f106a136ab951a5e'",
                      self.client.out)
        self.assertIn("Uploading package 1/1", self.client.out)

    def test_revision_delete_latest(self):
        # Pending to better index
        pass
