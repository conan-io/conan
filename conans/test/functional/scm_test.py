import os
import unittest

from conans.client.tools.scm import Git
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load

base = '''
from conans import ConanFile, tools

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    short_paths = True
    scm = {{
        "type": "git",
        "directory": {directory},
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
        self.client.runner("git add .", cwd=self.client.current_folder)
        self.client.runner('git commit -m  "commiting"', cwd=self.client.current_folder)

    def test_auto_git(self):
        curdir = self.client.current_folder
        conanfile = base.format(directory="None", url="auto", revision="auto")
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self._commit_contents()
        error = self.client.run("export . user/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Repo origin cannot be deduced by 'auto', using source folder",
                      self.client.out)

        self.client.runner('git remote add origin https://myrepo.com.git', cwd=curdir)

        # Create the package, will copy the sources from the local folder
        self.client.run("create . user/channel")
        sources_dir = self.client.client_cache.local_sources_pointer(self.reference)
        self.assertEquals(load(sources_dir), curdir)
        self.assertIn("Repo origin deduced by 'auto': https://myrepo.com.git", self.client.out)
        self.assertIn("Revision deduced by 'auto'", self.client.out)
        self.assertIn("Getting sources from folder: %s" % curdir, self.client.out)
        self.assertIn("My file is copied", self.client.out)

        # Export again but now with absolute reference, so no pointer file is created nor kept
        git = Git(curdir)
        self.client.save({"conanfile.py": base.format(directory="None",
                                                      url=curdir, revision=git.get_revision())})
        self.client.run("create . user/channel")
        sources_dir = self.client.client_cache.local_sources_pointer(self.reference)
        self.assertFalse(os.path.exists(sources_dir))
        self.assertNotIn("Repo origin deduced by 'auto'", self.client.out)
        self.assertNotIn("Revision deduced by 'auto'", self.client.out)
        self.assertIn("Getting sources from url: '%s'" % curdir, self.client.out)
        self.assertIn("My file is copied", self.client.out)

    def test_local_source(self):
        curdir = self.client.current_folder
        conanfile = base.format(directory="None", url="auto", revision="auto")
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self._commit_contents()
        self.client.save({"aditional_file.txt": "contents"})

        self.client.run("source . --source-folder=./source")
        self.assertTrue(os.path.exists(os.path.join(curdir, "source", "myfile.txt")))
        # Even the not commited files are copied
        self.assertTrue(os.path.exists(os.path.join(curdir, "source", "aditional_file.txt")))
        self.assertIn("Getting sources from folder: %s" % curdir, self.client.out)

        # Export again but now with absolute reference, so no pointer file is created nor kept
        git = Git(curdir)
        self.client.save({"conanfile.py": base.format(directory="None",
                                                      url=curdir, revision=git.get_revision()),
                          "myfile2.txt": "My file is copied"})
        self._commit_contents()
        self.client.run("source . --source-folder=./source2")
        # myfile2 is no in the specified commit
        self.assertFalse(os.path.exists(os.path.join(curdir, "source2", "myfile2.txt")))
        self.assertTrue(os.path.exists(os.path.join(curdir, "source2", "myfile.txt")))
        self.assertIn("Getting sources from url: '%s'" % curdir, self.client.out)

    def test_install_checked_out(self):
        test_server = TestServer()
        self.servers = {"myremote": test_server}
        self.client = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})

        curdir = self.client.current_folder
        conanfile = base.format(directory="None", url="auto", revision="auto")
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self._commit_contents()
        cmd = 'git remote add origin "%s"' % curdir
        print(cmd)
        self.client.runner(cmd, cwd=curdir)
        self.client.run("export . lasote/channel")
        self.client.run("upload lib* -c")

        # Take other client, the old client folder will be used as a remote
        client2 = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})
        client2.run("install lib/0.1@lasote/channel --build")
        self.assertIn("My file is copied", client2.out)


