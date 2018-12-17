import os
import time
import unittest
from collections import OrderedDict
from time import sleep

from conans import DEFAULT_REVISION_V1, REVISIONS, load
from conans.client.tools import environment_append
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, \
    create_local_git_repo


@unittest.skipUnless(TestClient().revisions,
                     "The test needs revisions activated, set CONAN_CLIENT_REVISIONS_ENABLED=1")
class RevisionsTest(unittest.TestCase):

    def setUp(self):
        self.servers = OrderedDict()
        self.users = {}
        for i in range(3):
            self.servers["remote%d" % i] = TestServer(server_capabilities=[REVISIONS])
            self.users["remote%d" % i] = [("lasote", "mypass")]

        self.servers["remote_norevisions"] = TestServer(server_capabilities=[])
        self.users["remote_norevisions"] = [("lasote", "mypass")]
        self.client = TestClient(servers=self.servers, users=self.users)
        self.conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    def build(self):
        self.output.warn("Revision 1")        
'''
        self.ref = ConanFileReference.loads("lib/1.0@lasote/testing")

    def _create_and_upload(self, conanfile, reference, remote=None, args=""):
        remote = remote or "remote0"
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . %s %s" % (str(reference), args))
        self.client.run("upload %s -c --all -r %s" % (str(reference), remote))

    def test_revisions_recipes_without_scm(self):

        self._create_and_upload(self.conanfile, self.ref)
        rev = self.servers["remote0"].server_store.get_last_revision(self.ref).revision
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

    def test_revision_with_fixed_scm(self):

        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    scm = {"type": "git",
           "url": "auto",
           "revision": "fixed_revision"}       
'''
        path, commit = create_local_git_repo({"myfile": "contents",
                                              "conanfile.py": conanfile}, branch="my_release")
        self.client.current_folder = path
        self.client.runner('git remote add origin https://myrepo.com.git', cwd=path)
        self.client.save({"conanfile.py": conanfile})
        self.client.run("export . %s " % str(self.ref))
        rev = self.client.get_revision(self.ref)
        self.assertNotEqual(rev, "fixed_revision")

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
        with environment_append({"PACKAGE_CONTENTS": "1"}):
            self._create_and_upload(conanfile, self.ref)
        rev = self.servers["remote0"].server_store.get_last_revision(self.ref).revision
        self.assertEquals(rev, "202f9ce41808083a0f0c0d071fb5f398")

        self.ref = self.ref.copy_with_rev(rev)
        p_ref = PackageReference(self.ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        pkg_rev = self.servers["remote0"].server_store.get_last_package_revision(p_ref).revision
        self.assertEquals(pkg_rev, "15ab113a16e2ac8c9ecffb4ba48306b2")

        # Create new package revision for the same recipe
        with environment_append({"PACKAGE_CONTENTS": "2"}):
            self._create_and_upload(conanfile, self.ref.copy_clear_rev())
        pkg_rev = self.servers["remote0"].server_store.get_last_package_revision(p_ref).revision
        self.assertEquals(pkg_rev, "8e54c6ea967722f2f9bdcbacb21792f5")

        # Delete all from local
        self.client.run("remove %s -f" % str(self.ref.copy_clear_rev()))

        # Download specifying recipe with revisions and package with revisions
        self.client.run("download %s -p 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#"
                        "8e54c6ea967722f2f9bdcbacb21792f5" % self.ref.full_repr())

        contents = load(os.path.join(self.client.client_cache.package(p_ref), "myfile.txt"))
        self.assertEquals(contents, "2")

        # Download previous package revision
        self.client.run("download %s -p 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#"
                        "15ab113a16e2ac8c9ecffb4ba48306b2" % self.ref.full_repr())
        contents = load(os.path.join(self.client.client_cache.package(p_ref), "myfile.txt"))
        self.assertEquals(contents, "1")

        # Specify a package revision without a recipe revision
        self.client.run("download %s -p 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#"
                        "15ab113a16e2ac8c9ecffb4ba48306b2" % str(self.ref),
                        assert_error=True)
        self.assertIn("It is needed to specify the recipe revision if "
                      "you specify a package revision", self.client.out)

    def test_search_with_revision(self):
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    settings = "os"
    def build(self):
        self.output.warn("Revision 1")
'''
        self._create_and_upload(conanfile, self.ref, args="-s os=Linux")
        rev1 = self.servers["remote0"].server_store.get_last_revision(self.ref).revision
        self._create_and_upload(conanfile.replace('"os"', '"arch"'), self.ref, args="-s arch=x86")
        rev2 = self.servers["remote0"].server_store.get_last_revision(self.ref).revision
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

        self.client.current_folder = path
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev_server = self.servers["remote0"].server_store.get_last_revision(self.ref)
        self.assertEqual(commit, rev_server.revision)

        self.client.run("remove %s -f" % str(self.ref))
        self.client.run("install %s#%s" % (str(self.ref), rev_server.revision))
        self.assertIn("Package installed 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", self.client.out)

        self.client.run("remove %s -f" % str(self.ref))
        self.client.run("install %s" % str(self.ref))
        self.assertIn("Package installed 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", self.client.out)

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

        self.client.client_cache.registry.refs.remove(self.ref)
        # Upload to a non-revisions server, the revision should be always there in the registry
        self._create_and_upload(conanfile, self.ref, args="-s os=Linux", remote="remote_norevisions")
        self.client.run("info %s" % str(self.ref))
        self.assertIn("Revision: c5485544fd84cf85e45cc742feb8b34c", self.client.out)

    def test_update_recipe(self):
        self.client.save({"conanfile.py": self.conanfile})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        self.client.run("remote list_ref")

        pref = PackageReference.loads("lib/1.0@lasote/testing:"
                                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertIn("%s: remote0" % str(self.ref), self.client.out)
        self.client.run("remote list_pref %s" % str(self.ref))
        self.assertIn("%s: remote0" % str(pref), self.client.out)

        rev = self.client.get_revision(self.ref)
        self.assertEquals(rev, "149570a812b46d87c7dfa6408809b370")

        sleep(1)
        client2 = TestClient(servers=self.servers, users=self.users)
        conanfile2 = self.conanfile + "# Holaaa "
        client2.save({"conanfile.py": conanfile2})
        client2.run("create . %s" % str(self.ref))
        client2.run("upload %s -c --all -r remote0" % str(self.ref))
        client2.run("remote list_pref %s" % str(self.ref))

        rev = client2.get_revision(self.ref)
        self.assertEquals(rev, "621568e8053761d685dcf1bfbe3b3f10")

        # install of the client1 (no-update)
        self.client.run("install %s" % str(self.ref))
        self.assertIn("lib/1.0@lasote/testing from 'remote0' - Cache", self.client.out)
        self.assertIn("%s - Cache" % str(pref), self.client.out)
        self.client.run("remote list_pref %s" % str(self.ref))
        self.assertIn("%s: remote0" % str(pref), self.client.out)

        rev = self.client.get_revision(self.ref)
        self.assertEquals(rev, "149570a812b46d87c7dfa6408809b370")

        # install with update
        self.client.run("install %s --update" % str(self.ref))
        rev = self.client.get_revision(self.ref)
        self.assertEquals(rev, "621568e8053761d685dcf1bfbe3b3f10")
        self.assertNotIn("%s from 'remote0' - Newer" % str(self.ref), self.client.out)
        self.assertIn("Outdated package! The package doesn't belong to the installed recipe "
                      "revision:", self.client.out)
        self.assertIn("%s from 'remote0' - Updated" % str(self.ref), self.client.out)
        self.assertIn("%s - Update" % str(pref), self.client.out)

    def test_registry_revision_updated(self):
        self.client.save({"conanfile.py": self.conanfile})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev = self.client.get_revision(self.ref)
        remote_rev = self.servers["remote0"].server_store.get_last_revision(self.ref)
        self.assertEquals(remote_rev.revision, rev)

        self.client.save({"conanfile.py": self.conanfile + " "})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev2 = self.client.get_revision(self.ref)
        remote_rev2 = self.servers["remote0"].server_store.get_last_revision(self.ref)
        self.assertEquals(remote_rev2.revision, rev2)
        self.assertNotEquals(rev, rev2)

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
        sleep(1)
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

    def test_conflict_with_different_revisions_but_same_ref(self):
        """Diamond requiring different revisions in the reference"""
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile): 
    pass
'''
        ref_a = ConanFileReference.loads("libA/1.0@lasote/testing")
        self._create_and_upload(conanfile, ref_a)
        rev = self.servers["remote0"].server_store.get_last_revision(ref_a).revision
        self._create_and_upload(conanfile + " ", ref_a)  # New revision
        rev2 = self.servers["remote0"].server_store.get_last_revision(ref_a).revision

        ref_b = ConanFileReference.loads("libB/1.0@lasote/testing")
        req = "%s#%s" % (ref_a, rev)
        self._create_and_upload(conanfile.replace("pass", 'requires = "%s"' % req), ref_b)

        ref_c = ConanFileReference.loads("libC/1.0@lasote/testing")
        req = "%s#%s" % (ref_a, rev2)
        self._create_and_upload(conanfile.replace("pass", 'requires = "%s"' % req), ref_c)

        ref_d = ConanFileReference.loads("libD/1.0@lasote/testing")
        repl = 'requires = "%s", "%s"' % (str(ref_c), str(ref_b))
        self.client.save({"conanfile.py": conanfile.replace("pass", repl)})
        self.client.run("create . %s" % str(ref_d), assert_error=True)

        self.assertIn("Different revisions of libA/1.0@lasote/testing "
                      "has been requested", self.client.out)

        self.client.run('remove "*" -f')
        self.client.run("create . %s" % str(ref_d), assert_error=True)
        self.client.run("create . %s" % str(ref_d), assert_error=True)
        self.assertIn("Different revisions of libA/1.0@lasote/testing "
                      "has been requested", self.client.out)

    def test_upload_not_overwrite(self):

        self.client.save({"conanfile.py": self.conanfile})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all --no-overwrite" % str(self.ref))
        self.client.save({"conanfile.py": self.conanfile + " "})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all --no-overwrite" % str(self.ref))

    def test_export_cleans_revision_in_registy(self):
        self.client.save({"conanfile.py": self.conanfile})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all --no-overwrite" % str(self.ref))

        # No changes
        self.client.save({"conanfile.py": self.conanfile})
        self.client.run("export . %s" % str(self.ref))
        cur_rev = self.client.get_revision(self.ref)
        self.assertIsNotNone(cur_rev)

        # Export new recipe, the revision is not cleared but changed
        self.client.save({"conanfile.py": self.conanfile + " "})
        self.client.run("export . %s" % str(self.ref))
        new_rev = self.client.get_revision(self.ref)
        self.assertIsNotNone(new_rev)
        self.assertNotEqual(cur_rev, new_rev)

    def test_alias_with_revisions(self):

        self.client.save({"conanfile.py": self.conanfile})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev = self.client.get_revision(self.ref)
        full_ref = self.ref.copy_with_rev(rev)

        self.client.save({"conanfile.py": self.conanfile.replace("Revision 1", "Revision 2")})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))

        alias = """from conans import ConanFile

class AliasConanfile(ConanFile):
    alias = "%s"
""" % full_ref.full_repr()

        self.client.save({"conanfile.py": alias})
        self.client.run("export . lib/snap@lasote/testing")
        # As we requested a different revision it will install the correct one
        self.client.run("install lib/snap@lasote/testing --build")
        self.assertIn("Revision 1", self.client.out)

    def test_recipe_revision_delete_all(self):
        self.client.save({"conanfile.py": self.conanfile})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))

        self.client.save({"conanfile.py": self.conanfile.replace("Revision 1", "Revision 2")})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        self.client.run("remove %s -r remote0 -f" % str(self.ref))

        last_rev = self.servers["remote0"].server_store.get_last_revision(self.ref)
        self.assertIsNone(last_rev)

    def test_recipe_revision_delete_one(self):
        # Upload revision1
        self.client.save({"conanfile.py": self.conanfile})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev = self.client.get_revision(self.ref)
        remote_rev = self.servers["remote0"].server_store.get_last_revision(self.ref)
        self.assertEquals(remote_rev.revision, rev)

        # Upload revision2
        self.client.save({"conanfile.py": self.conanfile.replace("Revision 1", "Revision 2")})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev2 = self.client.get_revision(self.ref)
        remote_rev = self.servers["remote0"].server_store.get_last_revision(self.ref)
        self.assertEquals(remote_rev.revision, rev2)

        # Remove revision2
        self.client.run("remove %s#%s -r remote0 -f" % (str(self.ref), rev2))
        remote_rev = self.servers["remote0"].server_store.get_last_revision(self.ref)
        self.assertEquals(remote_rev.revision, rev)

        # Upload revision3
        self.client.save({"conanfile.py": self.conanfile.replace("Revision 1", "Revision 3")})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev3 = self.client.get_revision(self.ref)
        self.assertNotEquals(rev3, rev2)
        remote_rev = self.servers["remote0"].server_store.get_last_revision(self.ref)
        self.assertEquals(remote_rev.revision, rev3)

        # Remove revision 3, remote is rev1
        self.client.run("remove %s#%s -r remote0 -f" % (str(self.ref), rev3))
        remote_rev = self.servers["remote0"].server_store.get_last_revision(self.ref)
        self.assertEquals(remote_rev.revision, rev)

    def test_remote_search(self):
        conanfile = '''
import time
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):
    settings = "os"
    def package(self):
        tools.save(os.path.join(self.package_folder, "file.txt"), str(time.time()))
'''
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . %s -s os=Windows" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev1 = self.servers["remote0"].server_store.get_last_revision(self.ref).revision
        # Create other recipe revision with a different binary package
        self.client.save({"conanfile.py": conanfile + " "})
        self.client.run("create . %s -s os=Linux" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev2 = self.servers["remote0"].server_store.get_last_revision(self.ref).revision
        # Search with revision1 (only win package available)
        self.client.run("search %s#%s -r remote0" % (str(self.ref), rev1))
        self.assertIn("Existing recipe in remote 'remote0'", self.client.out)
        self.assertIn("os: Windows", self.client.out)
        self.assertNotIn("os: Linux", self.client.out)
        # Search with revision2 (only linux package available)
        self.client.run("search %s#%s -r remote0" % (str(self.ref), rev2))
        self.assertIn("Existing recipe in remote 'remote0'", self.client.out)
        self.assertIn("os: Linux", self.client.out)
        self.assertNotIn("os: Windows", self.client.out)

    def _upload_two_revisions(self, ref, different_binary=False):
            conanfile = '''
import os
import uuid
from conans import ConanFile, tools

class HelloConan(ConanFile): 
    pass
'''
            if different_binary:  # Same pid but different binary hash
                conanfile += """
    def package(self):
        tools.save(os.path.join(self.package_folder, "file"), str(uuid.uuid4()))
"""
            self._create_and_upload(conanfile, ref)
            _rev1 = self.client.get_revision(ref)
            self._create_and_upload(conanfile + "\n", ref)
            _rev2 = self.client.get_revision(ref)
            return _rev1, _rev2

    def test_remove_recipe_v2_test(self):

        ref = ConanFileReference.loads("lib/1.0@lasote/testing")
        rev1, rev2 = self._upload_two_revisions(ref)

        # If I specify rev2 only rev2 is removed
        self.client.run("remove %s#%s -f -r remote0" % (str(ref), rev2))
        latestrev = self.servers["remote0"].server_store.get_last_revision(ref).revision
        self.assertEquals(latestrev, rev1)

        self._upload_two_revisions(ref)
        # If I don't specify revision all the revisions are removed
        self.client.run("remove %s -f -r remote0" % str(ref))
        latestrev = self.servers["remote0"].server_store.get_last_revision(ref)
        self.assertIsNone(latestrev)

    def test_remove_packages_v2_test(self):
        # If I don't specify a recipe revision it will remove all the packages from all recipe
        # revisions
        pid = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        ref = ConanFileReference.loads("lib/1.0@lasote/testing")
        rev1, rev2 = self._upload_two_revisions(ref)
        full_pr1 = PackageReference(ref.copy_with_rev(rev1), pid)
        full_pr2 = PackageReference(ref.copy_with_rev(rev2), pid)
        path1 = self.servers["remote0"].server_store.package(full_pr1)
        path2 = self.servers["remote0"].server_store.package(full_pr2)
        self.assertTrue(os.path.exists(path1))
        self.assertTrue(os.path.exists(path2))

        self.client.run("remove %s -f -r remote0 -p %s" % (str(ref), pid))
        self.assertFalse(os.path.exists(path1))
        self.assertFalse(os.path.exists(path2))

        # Now specify the recipe revision
        self._upload_two_revisions(ref)
        self.client.run("remove %s#%s -f -r remote0 -p %s" % (str(ref), rev1, pid))
        self.assertFalse(os.path.exists(path1))
        self.assertTrue(os.path.exists(path2))

        # Now generate different package revisions also
        rev1, rev2 = self._upload_two_revisions(ref, different_binary=True)
        full_pr1 = PackageReference(ref.copy_with_rev(rev1), pid)
        prevs = [el.revision for el in self.servers["remote0"].server_store.get_package_revisions(full_pr1)]
        self.assertEquals(len(prevs), 1)
        self._upload_two_revisions(ref, different_binary=True)
        prevs = [el.revision for el in self.servers["remote0"].server_store.get_package_revisions(full_pr1)]
        self.assertEquals(len(prevs), 2)

        # Remove a concrete package reference
        self.client.run("remove %s#%s -f -r remote0 -p %s#%s" % (str(ref), rev1, pid, prevs[0]))
        prevs_now = [el.revision
                     for el in self.servers["remote0"].server_store.get_package_revisions(full_pr1)]
        self.assertEquals(len(prevs_now), 1)
        self.assertEquals(prevs_now[0], prevs[1])

    def test_remove_all_revs_with_v1(self):
        # Check if v1 with several versions in the server will:
        # Remove all the revisions and packages if I remove by reference
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile): 
    pass
'''
        ref = ConanFileReference.loads("lib/1.0@lasote/testing")
        # Upload three revisions of A and its packages
        self._create_and_upload(conanfile, ref)
        rev1 = self.client.get_revision(ref)

        self._create_and_upload(conanfile + "\n", ref)
        rev2 = self.client.get_revision(ref)

        self._create_and_upload(conanfile + "\n\n", ref)
        rev3 = self.client.get_revision(ref)

        self._create_and_upload(conanfile + "\n\n\n", ref)
        rev4 = self.client.get_revision(ref)

        self.assertNotEquals(rev1, rev2)
        self.assertNotEquals(rev2, rev3)
        self.assertNotEquals(rev1, rev3)

        # Remove all locally
        self.client.run("remove '*' -f")

        # First a pre-check, if I remove only the package for the rev4 the rest is there
        self.client.run("remove %s#%s -f -r remote0" % (ref, rev4))
        latestrev = self.servers["remote0"].server_store.get_last_revision(ref).revision
        self.assertEquals(latestrev, rev3)
        self.client.run("install %s#%s" % (self.ref, rev3))

        # Create a v1 client and remove the pid
        client_no_rev = TestClient(block_v2=True, servers=self.servers, users=self.users)
        client_no_rev.run("remove %s -f -p 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 "
                          "-r remote0" % str(ref))

        # Remove all locally again
        self.client.run("remove '*' -f")

        # Use the regular v2 client and try to install specifying revisions
        self.client.run("install %s#%s" % (self.ref, rev1), assert_error=True)
        self.assertIn("Can't find a 'lib/1.0@lasote/testing' package", self.client.out)
        self.client.run("install %s#%s" % (self.ref, rev2), assert_error=True)
        self.assertIn("Can't find a 'lib/1.0@lasote/testing' package", self.client.out)
        self.client.run("install %s#%s" % (self.ref, rev3), assert_error=True)
        self.assertIn("Can't find a 'lib/1.0@lasote/testing' package", self.client.out)

    def test_v1_with_revisions_behavior(self):

        client_no_rev = TestClient(block_v2=True, servers=self.servers, users=self.users)
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    
    def build(self):
        self.output.warn("Hello")     
'''
        client_no_rev.save({"conanfile.py": conanfile})
        client_no_rev.run("create . %s" % str(self.ref))
        client_no_rev.run("upload %s -c --all -r remote0" % str(self.ref))

        rev1 = self.servers["remote0"].server_store.get_last_revision(self.ref).revision
        self.assertEquals(rev1, DEFAULT_REVISION_V1)

        # An upload from the other client with revisions puts a new revision as latest
        self.client.save({"conanfile.py": conanfile.replace("Hello", "Bye")})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))

        rev1 = self.servers["remote0"].server_store.get_last_revision(self.ref).revision
        self.assertNotEquals(rev1, DEFAULT_REVISION_V1)

        client_no_rev.run('remove "*" -f')
        client_no_rev.run("install %s --build" % str(self.ref))
        # Client v1 never receives revision but 0
        self.assertEquals(client_no_rev.get_revision(self.ref), DEFAULT_REVISION_V1)
        self.assertIn("Bye", client_no_rev.out)

        # If client v1 uploads again the recipe it is the latest again, but with rev0
        client_no_rev.save({"conanfile.py": conanfile.replace("Hello", "Foo")})
        client_no_rev.run("create . %s" % str(self.ref))
        client_no_rev.run("upload %s -c --all -r remote0" % str(self.ref))

        rev1 = self.servers["remote0"].server_store.get_last_revision(self.ref).revision
        self.assertEquals(rev1, DEFAULT_REVISION_V1)

        # Even for the client with revision, now the latest is 0
        self.client.run('remove "*" -f')
        self.client.run("install %s --build" % str(self.ref))
        self.assertIn("Foo", self.client.out)
        self.assertEquals(self.client.get_revision(self.ref), DEFAULT_REVISION_V1)

    def package_iterating_remote_same_recipe_revision_test(self):
        """If remote1 and remote2 has the same recipe revisions it will
        look for binaries iterating"""
        pid = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        # https://github.com/conan-io/conan/issues/3882
        conanfile = """from conans import ConanFile
class ConanFileToolsTest(ConanFile):
    pass
"""
        # Upload recipe + package to remote1 and remote2
        ref = "Hello/0.1@lasote/stable"
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . %s" % ref)
        self.client.run("upload %s -r=remote0 --all" % ref)
        self.client.run("upload %s -r=remote2 --all" % ref)

        # Remove only binary from remote1 and everything in local
        self.client.run("remove -f %s -p -r remote0" % ref)
        self.client.run('remove "*" -f')

        # Now install it from a client, it will find the binary in remote2
        # because the recipe revision is the same
        self.client.run("install %s" % ref)
        self.assertIn("Retrieving package %s from remote 'remote2' " % pid, self.client.out)

    def package_iterating_remote_different_recipe_revision_test(self):
        """If remote1 and remote2 has the same recipe revisions it wont
        look for binaries iterating"""
        # https://github.com/conan-io/conan/issues/3882
        conanfile = """from conans import ConanFile
class ConanFileToolsTest(ConanFile):
    pass
"""
        # Upload recipe + package to remote1 and remote2
        ref = "Hello/0.1@lasote/stable"
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . %s" % ref)
        self.client.run("upload %s -r=remote0 --all" % ref)

        self.client.save({"conanfile.py": conanfile + "\n"})
        self.client.run("create . %s" % ref)
        self.client.run("upload %s -r=remote2 --all" % ref)

        # Remove only binary from remote1 and everything in local
        self.client.run("remove -f %s -p -r remote0" % ref)
        self.client.run('remove "*" -f')

        # Now install it from a client, it won't find the binary in remote2
        # because the recipe revision is NOT the same
        self.client.run("install %s" % ref, assert_error=True)
        self.assertIn("Can't find a 'Hello/0.1@lasote/stable' package", self.client.out)


@unittest.skipUnless(TestClient().revisions,
                     "The test needs revisions activated, set CONAN_CLIENT_REVISIONS_ENABLED=1")
class CompatibilityRevisionsTest(unittest.TestCase):
    """Testing non breaking behavior from v1 and v2 with compatibility mode"""

    def setUp(self):
        self.servers = OrderedDict()
        self.servers["remote0"] = TestServer(server_capabilities=[REVISIONS])
        self.users = {"remote0": [("lasote", "mypass")],
                      "remote_norevisions": [("lasote", "mypass")]}
        self.servers["remote_norevisions"] = TestServer(server_capabilities=[])
        self.client = TestClient(servers=self.servers, users=self.users)
        self.conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    def build(self):
        self.output.warn("Revision 1")        
'''
        self.ref = ConanFileReference.loads("lib/1.0@lasote/testing")

    def test_search_v1_iterate_remotes(self):
        """Two recipe revisions, first with 1 binary, second with 1 binary, search v1 and v2
        with compatibility, have to find both"""
        conanfile = """from conans import ConanFile
class ConanFileToolsTest(ConanFile):
    settings = "os"
"""
        # Upload recipe + package to remote0
        ref = "Hello/0.1@lasote/stable"
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . %s -s os=Windows" % ref)
        self.client.run("upload %s -r=remote0 --all" % ref)

        conanfile += " "
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . %s -s os=Linux" % ref)
        self.client.run("upload %s -r=remote0 --all" % ref)

        client_no_rev = TestClient(block_v2=True, servers=self.servers, users=self.users)
        client_no_rev.run("search %s -r remote0" % ref)

        self.assertIn("3475bd55b91ae904ac96fde0f106a136ab951a5e", client_no_rev.out)
        self.assertIn("cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31", client_no_rev.out)

        client_compatibility = TestClient(block_v2=True, revisions=False,
                                          servers=self.servers, users=self.users)
        client_compatibility.run("search %s -r remote0" % ref)
        self.assertIn("3475bd55b91ae904ac96fde0f106a136ab951a5e", client_compatibility.out)
        self.assertIn("cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31", client_compatibility.out)

        # And not repeated even if duplicated in remote
        self.client.run("create . %s -s os=Windows" % ref)
        self.client.run("upload %s -r=remote0 --all" % ref)

        client_no_rev.run("search %s -r remote0" % ref)

        self.assertEquals(str(client_no_rev.out).count("3475bd55b91ae904ac96fde0f106a136ab951a5e"),
                          1)
        self.assertEquals(str(client_no_rev.out).count("cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31"),
                          1)

    def test_remove_packages_from_recipe_revision(self):
        """It shouldn't remove the packages for all recipe revisions but only for the specified
        if a recipe revision is specified"""
        conanfile = """from conans import ConanFile
class ConanFileToolsTest(ConanFile):
    pass
"""
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")

        # Upload recipe rev 1 + package to remote0
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . %s" % str(ref))
        self.client.run("upload %s -r=remote0 --all" % str(ref))
        rev1 = self.client.get_revision(ref)

        # Upload recipe rev 2 + package to remote0
        self.client.save({"conanfile.py": conanfile + "\n"})
        self.client.run("create . %s" % str(ref))
        self.client.run("upload %s -r=remote0 --all" % str(ref))
        rev2 = self.client.get_revision(ref)

        # Remove the binaries from the recipe rev1
        self.client.run("remove %s#%s -p -r=remote0 -f" % (str(ref), rev1))
        self.client.run("remove %s -f" % str(ref))

        # Try to install binaries from the rev1, it should fail
        self.client.run("install %s#%s" % (str(ref), rev1), assert_error=True)
        self.assertIn("Missing prebuilt package for 'Hello/0.1@lasote/stable", self.client.out)

        # Try to install binaries from the rev2, it should succeed
        self.client.run("install %s#%s" % (str(ref), rev2))

        # Also try without specifying revision
        self.client.run("remove %s -f" % str(ref))
        self.client.run("install %s" % str(ref))

    def test_install_recipe_revision(self):
        """ Specifying the revision, it has to install that revision.
        """
        conanfile = """from conans import ConanFile
class ConanFileToolsTest(ConanFile):
    pass
"""
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")

        # Upload recipe rev 1 + package to remote0
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . %s" % str(ref))
        self.client.run("upload %s -r=remote0 --all" % str(ref))
        rev1 = self.client.get_revision(ref)

        # Upload recipe rev 2 + package to remote0
        self.client.save({"conanfile.py": conanfile + "\n#Comment for rev2"})
        self.client.run("create . %s" % str(ref))
        self.client.run("upload %s -r=remote0 --all" % str(ref))
        rev2 = self.client.get_revision(ref)

        self.assertNotEqual(rev1, rev2)

        # Remove all from local
        self.client.run("remove %s -f" % str(ref))

        # Try to install rev1 and not rev2
        self.client.run("install %s#%s" % (str(ref), rev1))
        conanfile_path = self.client.client_cache.conanfile(ref)
        contents = load(conanfile_path)
        self.assertNotIn("#Comment for rev2", contents)

        # Remove all from local
        self.client.run("remove %s -f" % str(ref))

        # Try to install rev2 and not rev1
        self.client.run("install %s#%s" % (str(ref), rev2))
        conanfile_path = self.client.client_cache.conanfile(ref)
        contents = load(conanfile_path)
        self.assertIn("#Comment for rev2", contents)

    def test_update_from_same_revision_test(self):
        """ If I specify conan install ref#revision --update it has to update to the latest binary
        of the same recipe.
        """
        conanfile = """
import time
import os
from conans import ConanFile, tools
class ConanFileToolsTest(ConanFile):
        
        def package(self):
            tools.save(os.path.join(self.package_folder, "file.txt"), str(time.time()))
"""
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")

        # Generate recipe rev 1 + package rev1 to remote0
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . %s" % str(ref))
        self.client.run("upload %s -r=remote0 --all" % str(ref))
        rev1 = self.client.get_revision(ref)
        package_ref = PackageReference(ref.copy_with_rev(rev1), NO_SETTINGS_PACKAGE_ID)
        prev1 = self.client.servers["remote0"].server_store.get_last_package_revision(package_ref).revision

        # Use another client to install the only binary revision for ref
        client2 = TestClient(servers=self.servers, users=self.users)
        client2.run("install %s" % str(ref))

        # Generate recipe rev1 + package rev2 to remote0
        time.sleep(1)
        self.client.run("remove %s -f" % str(ref))
        self.client.run("create . %s" % str(ref))
        self.client.run("upload %s -r=remote0 --all" % str(ref))
        rev1_ = self.client.get_revision(ref)
        self.assertEquals(rev1, rev1_)
        package_ref = PackageReference(ref.copy_with_rev(rev1), NO_SETTINGS_PACKAGE_ID)
        prev2 = self.client.servers["remote0"].server_store.get_last_package_revision(package_ref).revision
        self.assertNotEqual(prev1, prev2)  # Verify a new package revision is uploaded

        # Generate another recipe revision (and also bin revision)
        self.client.save({"conanfile.py": conanfile + "\n"})
        self.client.run("create . %s" % str(ref))
        self.client.run("upload %s -r=remote0 --all" % str(ref))

        # So, from client2 I install --update pinning the first recipe revision,
        # I don't want the recipe to be updated but the binary
        client2.run("install %s#%s --update" % (str(ref), rev1))
        self.assertNotIn("Hello/0.1@lasote/stable from 'remote0' - Updated", client2.out)
        self.assertIn("Hello/0.1@lasote/stable:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Update", client2.out)
        prev_ = client2.get_package_revision(package_ref)
        self.assertEquals(prev_, prev2)

    def old_server_new_client_simple_test(self):
        """Use this test as an example to try some new behavior with revisions against a server
        without revisions"""
        old_server = TestServer(server_capabilities=[])
        users = {"old_server": [("lasote", "mypass")]}
        client = TestClient(servers={"old_server": old_server}, users=users)
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    def build(self):
        self.output.warn("Revision 1")        
'''
        ref = ConanFileReference.loads("lib/1.0@lasote/testing")
        client.save({"conanfile.py": conanfile + "\n"})
        client.run("create . %s" % str(ref))
        client.run("upload %s -r=old_server --all" % str(ref))
        client.run("remove %s -f" % str(ref))
        client.run("install %s" % str(ref))
        package_ref = PackageReference(ref.copy_with_rev(DEFAULT_REVISION_V1),
                                       NO_SETTINGS_PACKAGE_ID)
        prev2 = client.servers["old_server"].server_store.get_last_package_revision(package_ref)
        self.assertEquals(prev2.revision, DEFAULT_REVISION_V1)
