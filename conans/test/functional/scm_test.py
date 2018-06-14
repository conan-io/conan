import json
import os
import unittest

from conans.client.tools.scm import Git
from conans.model.ref import ConanFileReference
from conans.model.scm import SCM
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestServer, create_local_git_repo
from conans.util.files import load, rmdir

base = '''
from conans import ConanFile, tools

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    short_paths = True
    scm = {{
        "type": "git",
        "url": "{url}",
        "revision": "{revision}",
    }}

    def build(self):
        self.output.warn(tools.load("myfile.txt"))
'''


class SCMTest(unittest.TestCase):

    def setUp(self):
        self.reference = ConanFileReference.loads("lib/0.1@user/channel")
        self.client = TestClient()

    def _commit_contents(self):
        self.client.runner("git init .", cwd=self.client.current_folder)
        self.client.runner('git config user.email "you@example.com"', cwd=self.client.current_folder)
        self.client.runner('git config user.name "Your Name"', cwd=self.client.current_folder)
        self.client.runner("git add .", cwd=self.client.current_folder)
        self.client.runner('git commit -m  "commiting"', cwd=self.client.current_folder)

    def test_scm_other_type_ignored(self):
        conanfile = '''
from conans import ConanFile, tools

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    scm = ["Other stuff"]

'''
        self.client.save({"conanfile.py": conanfile})
        # nothing breaks
        self.client.run("export . user/channel")

    def test_repeat_clone_changing_subfolder(self):
        tmp = '''
from conans import ConanFile, tools

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    scm = {{
        "type": "git",
        "url": "{url}",
        "revision": "{revision}",
        "subfolder": "onesubfolder"
    }}
'''
        path, commit = create_local_git_repo({"myfile": "contents"}, branch="my_release")
        conanfile = tmp.format(url=path, revision=commit)
        self.client.save({"conanfile.py": conanfile,
                          "myfile.txt": "My file is copied"})
        self.client.run("create . user/channel")
        conanfile = conanfile.replace('"onesubfolder"', '"othersubfolder"')
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . user/channel")
        folder = self.client.client_cache.source(ConanFileReference.loads("lib/0.1@user/channel"))
        self.assertIn("othersubfolder", os.listdir(folder))

    def test_auto_git(self):
        curdir = self.client.current_folder.replace("\\", "/")
        conanfile = base.format(directory="None", url="auto", revision="auto")
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self._commit_contents()
        error = self.client.run("export . user/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Repo origin cannot be deduced by 'auto'",
                      self.client.out)

        self.client.runner('git remote add origin https://myrepo.com.git', cwd=curdir)

        # Create the package, will copy the sources from the local folder
        self.client.run("create . user/channel")
        sources_dir = self.client.client_cache.scm_folder(self.reference)
        self.assertEquals(load(sources_dir), curdir)
        self.assertIn("Repo origin deduced by 'auto': https://myrepo.com.git", self.client.out)
        self.assertIn("Revision deduced by 'auto'", self.client.out)
        self.assertIn("Getting sources from folder: %s" % curdir, self.client.out)
        self.assertIn("My file is copied", self.client.out)

        # Export again but now with absolute reference, so no pointer file is created nor kept
        git = Git(curdir)
        self.client.save({"conanfile.py": base.format(url=curdir, revision=git.get_revision())})
        self.client.run("create . user/channel")
        sources_dir = self.client.client_cache.scm_folder(self.reference)
        self.assertFalse(os.path.exists(sources_dir))
        self.assertNotIn("Repo origin deduced by 'auto'", self.client.out)
        self.assertNotIn("Revision deduced by 'auto'", self.client.out)
        self.assertIn("Getting sources from url: '%s'" % curdir, self.client.out)
        self.assertIn("My file is copied", self.client.out)

    def test_deleted_source_folder(self):
        path, commit = create_local_git_repo({"myfile": "contents"}, branch="my_release")
        curdir = self.client.current_folder.replace("\\", "/")
        conanfile = base.format(url="auto", revision="auto")
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self._commit_contents()
        self.client.runner('git remote add origin "%s"' % path.replace("\\", "/"), cwd=curdir)
        self.client.run("export . user/channel")

        new_curdir = temp_folder()
        self.client.current_folder = new_curdir
        # delete old source, so it will try to checkout the remote because of the missing local dir
        rmdir(curdir)
        error = self.client.run("install lib/0.1@user/channel --build", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Getting sources from url: '%s'" % path.replace("\\", "/"), self.client.out)

    def test_local_source(self):
        curdir = self.client.current_folder
        conanfile = base.format(url="auto", revision="auto")
        conanfile += """
    def source(self):
        self.output.warn("SOURCE METHOD CALLED")
"""
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self._commit_contents()
        self.client.save({"aditional_file.txt": "contents"})

        self.client.run("source . --source-folder=./source")
        self.assertTrue(os.path.exists(os.path.join(curdir, "source", "myfile.txt")))
        self.assertIn("SOURCE METHOD CALLED", self.client.out)
        # Even the not commited files are copied
        self.assertTrue(os.path.exists(os.path.join(curdir, "source", "aditional_file.txt")))
        self.assertIn("Getting sources from folder: %s" % curdir, self.client.out)

        # Export again but now with absolute reference, so no pointer file is created nor kept
        git = Git(curdir.replace("\\", "/"))
        conanfile = base.format(url=curdir.replace("\\", "/"), revision=git.get_revision())
        conanfile += """
    def source(self):
        self.output.warn("SOURCE METHOD CALLED")
"""
        self.client.save({"conanfile.py": conanfile,
                          "myfile2.txt": "My file is copied"})
        self._commit_contents()
        self.client.run("source . --source-folder=./source2")
        # myfile2 is no in the specified commit
        self.assertFalse(os.path.exists(os.path.join(curdir, "source2", "myfile2.txt")))
        self.assertTrue(os.path.exists(os.path.join(curdir, "source2", "myfile.txt")))
        self.assertIn("Getting sources from url: '%s'" % curdir.replace("\\", "/"), self.client.out)
        self.assertIn("SOURCE METHOD CALLED", self.client.out)

    def test_install_checked_out(self):
        test_server = TestServer()
        self.servers = {"myremote": test_server}
        self.client = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})

        curdir = self.client.current_folder.replace("\\", "/")
        conanfile = base.format(url="auto", revision="auto")
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self._commit_contents()
        cmd = 'git remote add origin "%s"' % curdir
        self.client.runner(cmd, cwd=curdir)
        self.client.run("export . lasote/channel")
        self.client.run("upload lib* -c")

        # Take other client, the old client folder will be used as a remote
        client2 = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})
        client2.run("install lib/0.1@lasote/channel --build")
        self.assertIn("My file is copied", client2.out)

    def test_source_method_export_sources_and_scm_mixed(self):
        path, commit = create_local_git_repo({"myfile": "contents"}, branch="my_release")

        conanfile = '''
import os
from conans import ConanFile, tools

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    exports_sources = "file.txt"
    scm = {
        "type": "git",
        "url": "%s",
        "revision": "my_release",
        "subfolder": "src"
    }

    def source(self):
        self.output.warn("SOURCE METHOD CALLED")
        assert(os.path.exists("file.txt"))
        assert(os.path.exists(os.path.join("src", "myfile")))
        tools.save("cosa.txt", "contents")

    def build(self):
        assert(os.path.exists("file.txt"))
        assert(os.path.exists("cosa.txt"))
        self.output.warn("BUILD METHOD CALLED")
''' % path
        self.client.save({"conanfile.py": conanfile, "file.txt": "My file is copied"})
        self.client.run("create . user/channel")
        self.assertIn("SOURCE METHOD CALLED", self.client.out)
        self.assertIn("BUILD METHOD CALLED", self.client.out)

    def scm_serialization_test(self):
        data = {"url": "myurl", "revision": "myrevision", "username": "myusername",
                "password": "mypassword", "type": "git", "verify_ssl": True,
                "subfolder": "mysubfolder"}
        scm = SCM(data, temp_folder())
        the_json = str(scm)
        data2 = json.loads(the_json)
        self.assertEquals(data, data2)
