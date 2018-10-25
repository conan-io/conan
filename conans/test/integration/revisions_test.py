import os
import unittest
from collections import OrderedDict
from time import sleep

from conans import tools, REVISIONS
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, TestServer, create_local_git_repo


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
                        "7200b02593a12d8cf214c92ddf805ea9" % self.ref.full_repr())

        contents = tools.load(os.path.join(self.client.paths.package(p_ref), "myfile.txt"))
        self.assertEquals(contents, "2")

        # Download previous package revision
        self.client.run("download %s -p 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#"
                        "e18c97f441d104e8be42d1ad7e9d425d" % self.ref.full_repr())
        contents = tools.load(os.path.join(self.client.paths.package(p_ref), "myfile.txt"))
        self.assertEquals(contents, "1")

        # Specify a package revision without a recipe revision
        error = self.client.run("download %s -p 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#"
                                "e18c97f441d104e8be42d1ad7e9d425d" % str(self.ref),
                                ignore_error=True)
        self.assertTrue(error)
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

        self.client.remote_registry.refs.remove(self.ref)
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
        remote_rev = self.servers["remote0"].paths.get_last_revision(self.ref)
        self.assertEquals(remote_rev, rev)

        self.client.save({"conanfile.py": self.conanfile + " "})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev2 = self.client.get_revision(self.ref)
        remote_rev2 = self.servers["remote0"].paths.get_last_revision(self.ref)
        self.assertEquals(remote_rev2, rev2)
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
        rev = self.servers["remote0"].paths.get_last_revision(ref_a)
        self._create_and_upload(conanfile + " ", ref_a)  # New revision
        rev2 = self.servers["remote0"].paths.get_last_revision(ref_a)

        ref_b = ConanFileReference.loads("libB/1.0@lasote/testing")
        req = "%s#%s" % (ref_a, rev)
        self._create_and_upload(conanfile.replace("pass", 'requires = "%s"' % req), ref_b)

        ref_c = ConanFileReference.loads("libC/1.0@lasote/testing")
        req = "%s#%s" % (ref_a, rev2)
        self._create_and_upload(conanfile.replace("pass", 'requires = "%s"' % req), ref_c)

        ref_d = ConanFileReference.loads("libD/1.0@lasote/testing")
        repl = 'requires = "%s", "%s"' % (str(ref_c), str(ref_b))
        self.client.save({"conanfile.py": conanfile.replace("pass", repl)})
        error = self.client.run("create . %s" % str(ref_d), ignore_error=True)

        self.assertTrue(error)
        self.assertIn("Different revisions of libA/1.0@lasote/testing "
                      "has been requested", self.client.out)

        self.client.run('remove "*" -f')
        self.client.run("create . %s" % str(ref_d), ignore_error=True)
        error = self.client.run("create . %s" % str(ref_d), ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Different revisions of libA/1.0@lasote/testing "
                      "has been requested", self.client.out)

    def test_upload_not_overwrite(self):

        self.client.save({"conanfile.py": self.conanfile})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all --no-overwrite" % str(self.ref))
        self.assertIn("Remote 'remote0' uses revisions, argument '--no-overwrite' is useless",
                      self.client.out)
        self.client.save({"conanfile.py": self.conanfile + " "})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all --no-overwrite" % str(self.ref))
        self.assertIn("Remote 'remote0' uses revisions, argument '--no-overwrite' is useless",
                      self.client.out)

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
        full_ref = self.ref.copy_with_revision(rev)

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

        last_rev = self.servers["remote0"].paths.get_last_revision(self.ref)
        self.assertIsNone(last_rev)

    def test_recipe_revision_delete_one(self):
        # Upload revision1
        self.client.save({"conanfile.py": self.conanfile})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev = self.client.get_revision(self.ref)
        remote_rev = self.servers["remote0"].paths.get_last_revision(self.ref)
        self.assertEquals(remote_rev, rev)

        # Upload revision2
        self.client.save({"conanfile.py": self.conanfile.replace("Revision 1", "Revision 2")})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev2 = self.client.get_revision(self.ref)
        remote_rev = self.servers["remote0"].paths.get_last_revision(self.ref)
        self.assertEquals(remote_rev, rev2)

        # Remove revision2
        self.client.run("remove %s#%s -r remote0 -f" % (str(self.ref), rev2))
        remote_rev = self.servers["remote0"].paths.get_last_revision(self.ref)
        self.assertEquals(remote_rev, rev)

        # Upload revision3
        self.client.save({"conanfile.py": self.conanfile.replace("Revision 1", "Revision 3")})
        self.client.run("create . %s" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev3 = self.client.get_revision(self.ref)
        self.assertNotEquals(rev3, rev2)
        remote_rev = self.servers["remote0"].paths.get_last_revision(self.ref)
        self.assertEquals(remote_rev, rev3)

        # Remove revision 3, remote is rev1
        self.client.run("remove %s#%s -r remote0 -f" % (str(self.ref), rev3))
        remote_rev = self.servers["remote0"].paths.get_last_revision(self.ref)
        self.assertEquals(remote_rev, rev)

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
        rev1 = self.servers["remote0"].paths.get_last_revision(self.ref)
        # Create other recipe revision with a different binary package
        self.client.save({"conanfile.py": conanfile + " "})
        self.client.run("create . %s -s os=Linux" % str(self.ref))
        self.client.run("upload %s -c --all -r remote0" % str(self.ref))
        rev2 = self.servers["remote0"].paths.get_last_revision(self.ref)
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

    def test_revision_remove(self):
        # Pending to better index
        # Remove all by global ref?
        # Remove by ref + rev
        # Remove all packages in a ref
        # Remove one package in a ref (last) (check dirs cleaned)
        # Remove one revision of a package
        pass



