import json
import os
import unittest
from collections import namedtuple

from conans.client.tools.scm import Git, SVN
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.scm import SCMData
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestServer, create_local_git_repo, SVNLocalRepoTestCase
from conans.util.files import load, rmdir, save, to_file_bytes
from conans.client.tools.win import get_cased_path


base = '''
import os
from conans import ConanFile, tools

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    short_paths = True
    scm = {{
        "type": "%s",
        "url": "{url}",
        "revision": "{revision}",
    }}

    def build(self):
        sf = self.scm.get("subfolder")
        path = os.path.join(sf, "myfile.txt") if sf else "myfile.txt"
        self.output.warn(tools.load(path))
'''

base_git = base % "git"
base_svn = base % "svn"


class GitSCMTest(unittest.TestCase):

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
        self.assertTrue(os.path.exists(os.path.join(folder, "othersubfolder", "myfile")))

    def test_auto_filesystem_remote_git(self):
        # https://github.com/conan-io/conan/issues/3109
        conanfile = base_git.format(directory="None", url="auto", revision="auto")
        repo = temp_folder()
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"}, repo)
        self.client.runner("git init .", cwd=repo)
        self.client.runner('git config user.email "you@example.com"', cwd=repo)
        self.client.runner('git config user.name "Your Name"', cwd=repo)
        self.client.runner("git add .", cwd=repo)
        self.client.runner('git commit -m  "commiting"', cwd=repo)
        self.client.runner('git clone "%s" .' % repo, cwd=self.client.current_folder)
        self.client.run("export . user/channel")
        self.assertIn("WARN: Repo origin looks like a local path", self.client.out)
        os.remove(self.client.client_cache.scm_folder(ConanFileReference.loads("lib/0.1@user/channel")))
        self.client.run("install lib/0.1@user/channel --build")
        self.assertIn("lib/0.1@user/channel: Getting sources from url:", self.client.out)

    def test_auto_git(self):
        curdir = get_cased_path(self.client.current_folder).replace("\\", "/")
        conanfile = base_git.format(directory="None", url="auto", revision="auto")
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

        # check blank lines are respected in replacement
        self.client.run("get lib/0.1@user/channel")
        self.assertIn("""}

    def build(self):""", self.client.out)

        # Export again but now with absolute reference, so no pointer file is created nor kept
        git = Git(curdir)
        self.client.save({"conanfile.py": base_git.format(url=curdir, revision=git.get_revision())})
        self.client.run("create . user/channel")
        sources_dir = self.client.client_cache.scm_folder(self.reference)
        self.assertFalse(os.path.exists(sources_dir))
        self.assertNotIn("Repo origin deduced by 'auto'", self.client.out)
        self.assertNotIn("Revision deduced by 'auto'", self.client.out)
        self.assertIn("Getting sources from url: '%s'" % curdir, self.client.out)
        self.assertIn("My file is copied", self.client.out)

    def test_auto_subfolder(self):
        curdir = self.client.current_folder.replace("\\", "/")
        conanfile = base_git.replace('"revision": "{revision}"',
                                     '"revision": "{revision}",\n        '
                                     '"subfolder": "mysub"')
        conanfile = conanfile.replace("short_paths = True", "short_paths = False")
        conanfile = conanfile.format(directory="None", url="auto", revision="auto")
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self._commit_contents()
        self.client.runner('git remote add origin https://myrepo.com.git', cwd=curdir)
        self.client.run("create . user/channel")

        folder = self.client.client_cache.source(ConanFileReference.loads("lib/0.1@user/channel"))
        self.assertTrue(os.path.exists(os.path.join(folder, "mysub", "myfile.txt")))
        self.assertFalse(os.path.exists(os.path.join(folder, "mysub", "conanfile.py")))

    def test_auto_conanfile_no_root(self):
        """
        Conanfile is not in the root of the repo: https://github.com/conan-io/conan/issues/3465
        """
        curdir = get_cased_path(self.client.current_folder).replace("\\", "/")
        conanfile = base_git.format(url="auto", revision="auto")
        self.client.save({"conan/conanfile.py": conanfile, "myfile.txt": "content of my file"})
        self._commit_contents()
        self.client.runner('git remote add origin https://myrepo.com.git', cwd=curdir)

        # Create the package
        self.client.run("create conan/ user/channel")
        sources_dir = self.client.client_cache.scm_folder(self.reference)
        self.assertEquals(load(sources_dir), curdir.replace('\\', '/'))  # Root of git is 'curdir'

    def test_deleted_source_folder(self):
        path, commit = create_local_git_repo({"myfile": "contents"}, branch="my_release")
        curdir = self.client.current_folder.replace("\\", "/")
        conanfile = base_git.format(url="auto", revision="auto")
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

    def test_excluded_repo_fies(self):
        conanfile = base_git.format(url="auto", revision="auto")
        conanfile = conanfile.replace("short_paths = True", "short_paths = False")
        path, commit = create_local_git_repo({"myfile": "contents",
                                              "ignored.pyc": "bin",
                                              ".gitignore": """
*.pyc
my_excluded_folder
other_folder/excluded_subfolder
""",
                                              "myfile.txt": "My file!",
                                              "my_excluded_folder/some_file": "hey Apple!",
                                              "other_folder/excluded_subfolder/some_file": "hey Apple!",
                                              "other_folder/valid_file": "!",
                                              "conanfile.py": conanfile}, branch="my_release")
        self.client.current_folder = path
        self._commit_contents()
        self.client.runner('git remote add origin "%s"' % path.replace("\\", "/"), cwd=path)
        self.client.run("create . user/channel")
        self.assertIn("Copying sources to build folder", self.client.out)
        pref = PackageReference(ConanFileReference.loads("lib/0.1/user/channel"),
                                "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        bf = self.client.client_cache.build(pref)
        self.assertTrue(os.path.exists(os.path.join(bf, "myfile.txt")))
        self.assertTrue(os.path.exists(os.path.join(bf, "myfile")))
        self.assertTrue(os.path.exists(os.path.join(bf, ".git")))
        self.assertFalse(os.path.exists(os.path.join(bf, "ignored.pyc")))
        self.assertFalse(os.path.exists(os.path.join(bf, "my_excluded_folder")))
        self.assertTrue(os.path.exists(os.path.join(bf, "other_folder", "valid_file")))
        self.assertFalse(os.path.exists(os.path.join(bf, "other_folder", "excluded_subfolder")))

    def test_local_source(self):
        curdir = self.client.current_folder
        conanfile = base_git.format(url="auto", revision="auto")
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
        conanfile = base_git.format(url=curdir.replace("\\", "/"), revision=git.get_revision())
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

    def test_local_source_subfolder(self):
        curdir = self.client.current_folder
        conanfile = base_git.replace('"revision": "{revision}"',
                                     '"revision": "{revision}",\n        '
                                     '"subfolder": "mysub"')
        conanfile = conanfile.format(url="auto", revision="auto")
        conanfile += """
    def source(self):
        self.output.warn("SOURCE METHOD CALLED")
"""
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self._commit_contents()

        self.client.run("source . --source-folder=./source")
        self.assertFalse(os.path.exists(os.path.join(curdir, "source", "myfile.txt")))
        self.assertTrue(os.path.exists(os.path.join(curdir, "source", "mysub", "myfile.txt")))
        self.assertIn("SOURCE METHOD CALLED", self.client.out)

    def test_install_checked_out(self):
        test_server = TestServer()
        self.servers = {"myremote": test_server}
        self.client = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})

        curdir = self.client.current_folder.replace("\\", "/")
        conanfile = base_git.format(url="auto", revision="auto")
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

    def test_source_removed_in_local_cache(self):
        conanfile = '''
from conans import ConanFile, tools

class ConanLib(ConanFile):
    scm = {
        "type": "git",
        "url": "auto",
        "revision": "auto",
    }

    def build(self):
        contents = tools.load("myfile")
        self.output.warn("Contents: %s" % contents)

'''
        path, commit = create_local_git_repo({"myfile": "contents", "conanfile.py": conanfile},
                                             branch="my_release")
        self.client.current_folder = path
        self.client.runner('git remote add origin https://myrepo.com.git', cwd=path)
        self._commit_contents()

        self.client.run("create . lib/1.0@user/channel")
        self.assertIn("Contents: contents", self.client.out)
        self.client.save({"myfile": "Contents 2"})
        self.client.run("create . lib/1.0@user/channel")
        self.assertIn("Contents: Contents 2", self.client.out)
        self.assertIn("Detected 'scm' auto in conanfile, trying to remove source folder",
                      self.client.out)

    def test_submodule(self):
        subsubmodule, _ = create_local_git_repo({"subsubmodule": "contents"})
        submodule, _ = create_local_git_repo({"submodule": "contents"}, submodules=[subsubmodule])
        path, commit = create_local_git_repo({"myfile": "contents"}, branch="my_release", submodules=[submodule])

        def _relative_paths(folder):
            submodule_path = os.path.join(
                folder,
                os.path.basename(os.path.normpath(submodule)))
            subsubmodule_path = os.path.join(
                submodule_path,
                os.path.basename(os.path.normpath(subsubmodule)))
            return submodule_path, subsubmodule_path

        # Check old (default) behaviour
        tmp = '''
from conans import ConanFile, tools

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    scm = {{
        "type": "git",
        "url": "{url}",
        "revision": "{revision}"
    }}
'''
        conanfile = tmp.format(url=path, revision=commit)
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . user/channel")

        folder = self.client.client_cache.source(ConanFileReference.loads("lib/0.1@user/channel"))
        submodule_path, _ = _relative_paths(folder)
        self.assertTrue(os.path.exists(os.path.join(folder, "myfile")))
        self.assertFalse(os.path.exists(os.path.join(submodule_path, "submodule")))

        # Check invalid value
        tmp = '''
from conans import ConanFile, tools

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    scm = {{
        "type": "git",
        "url": "{url}",
        "revision": "{revision}",
        "submodule": "{submodule}"
    }}
'''
        conanfile = tmp.format(url=path, revision=commit, submodule="invalid")
        self.client.save({"conanfile.py": conanfile})

        error = self.client.run("create . user/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Invalid 'submodule' attribute value in the 'scm'.",
                      self.client.out)

        # Check shallow 
        conanfile = tmp.format(url=path, revision=commit, submodule="shallow")
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . user/channel")

        folder = self.client.client_cache.source(ConanFileReference.loads("lib/0.1@user/channel"))
        submodule_path, subsubmodule_path = _relative_paths(folder)
        self.assertTrue(os.path.exists(os.path.join(folder, "myfile")))
        self.assertTrue(os.path.exists(os.path.join(submodule_path, "submodule")))
        self.assertFalse(os.path.exists(os.path.join(subsubmodule_path, "subsubmodule")))

        # Check recursive
        conanfile = tmp.format(url=path, revision=commit, submodule="recursive")
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . user/channel")

        folder = self.client.client_cache.source(ConanFileReference.loads("lib/0.1@user/channel"))
        submodule_path, subsubmodule_path = _relative_paths(folder)
        self.assertTrue(os.path.exists(os.path.join(folder, "myfile")))
        self.assertTrue(os.path.exists(os.path.join(submodule_path, "submodule")))
        self.assertTrue(os.path.exists(os.path.join(subsubmodule_path, "subsubmodule")))

    def test_scm_bad_filename(self):
        # Fixes: #3500
        badfilename = "\xE3\x81\x82badfile.txt"
        path, _ = create_local_git_repo({"goodfile.txt": "good contents"}, branch="my_release")
        save(to_file_bytes(os.path.join(self.client.current_folder, badfilename)), "contents")
        self.client.runner('git remote add origin "%s"' % path.replace("\\", "/"), cwd=path)

        conanfile = '''
import os
from conans import ConanFile, tools

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    scm = {
        "type": "git",
        "url": "auto",
        "revision": "auto"
    }
    
    def build(self):
        pass
'''
        self.client.current_folder = path
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . user/channel")
        
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
        conanfile = namedtuple("ConanfileMock", "scm")(data)
        scm_data = SCMData(conanfile)
        the_json = str(scm_data)
        data2 = json.loads(the_json)
        self.assertEquals(data, data2)


class SVNSCMTest(SVNLocalRepoTestCase):

    def setUp(self):
        self.reference = ConanFileReference.loads("lib/0.1@user/channel")
        self.client = TestClient()

    def _commit_contents(self):
        # self.client.runner('svn co "{url}" "{path}"'.format(url=self.repo_url, path=self.client.current_folder))
        self.client.runner("svn add *", cwd=self.client.current_folder)
        self.client.runner('svn commit -m  "commiting"', cwd=self.client.current_folder)

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
        "type": "svn",
        "url": "{url}",
        "revision": "{revision}",
        "subfolder": "onesubfolder"
    }}
'''
        project_url, rev = self.create_project(files={"myfile": "contents"})
        conanfile = tmp.format(url=project_url, revision=rev)
        self.client.save({"conanfile.py": conanfile,
                          "myfile.txt": "My file is copied"})
        self.client.run("create . user/channel")
        conanfile = conanfile.replace('"onesubfolder"', '"othersubfolder"')
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . user/channel")
        folder = self.client.client_cache.source(ConanFileReference.loads("lib/0.1@user/channel"))
        self.assertIn("othersubfolder", os.listdir(folder))
        self.assertTrue(os.path.exists(os.path.join(folder, "othersubfolder", "myfile")))

    def test_auto_filesystem_remote_svn(self):
        # SVN origin will never be a local path (local repo has at least protocol file:///)
        pass

    def test_auto_svn(self):
        conanfile = base_svn.format(directory="None", url="auto", revision="auto")
        project_url, rev = self.create_project(files={"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        project_url = project_url.replace(" ", "%20")
        self.client.runner('svn co "{url}" "{path}"'.format(url=project_url, path=self.client.current_folder))

        curdir = self.client.current_folder.replace("\\", "/")
        # Create the package, will copy the sources from the local folder
        self.client.run("create . user/channel")
        sources_dir = self.client.client_cache.scm_folder(self.reference)
        self.assertEquals(load(sources_dir), curdir)
        self.assertIn("Repo origin deduced by 'auto': {}".format(project_url).lower(),
            str(self.client.out).lower())
        self.assertIn("Revision deduced by 'auto'", self.client.out)
        self.assertIn("Getting sources from folder: %s" % curdir, self.client.out)
        self.assertIn("My file is copied", self.client.out)

        # Export again but now with absolute reference, so no pointer file is created nor kept
        svn = SVN(curdir)
        self.client.save({"conanfile.py": base_svn.format(url=svn.get_remote_url(), revision=svn.get_revision())})
        self.client.run("create . user/channel", ignore_error=False)
        sources_dir = self.client.client_cache.scm_folder(self.reference)
        self.assertFalse(os.path.exists(sources_dir))
        self.assertNotIn("Repo origin deduced by 'auto'", self.client.out)
        self.assertNotIn("Revision deduced by 'auto'", self.client.out)
        self.assertIn("Getting sources from url: '{}'".format(project_url).lower(),
                      str(self.client.out).lower())
        self.assertIn("My file is copied", self.client.out)

    def test_auto_subfolder(self):
        conanfile = base_svn.replace('"revision": "{revision}"',
                                     '"revision": "{revision}",\n        '
                                     '"subfolder": "mysub"')
        conanfile = conanfile.replace("short_paths = True", "short_paths = False")
        conanfile = conanfile.format(directory="None", url="auto", revision="auto")

        project_url, rev = self.create_project(files={"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        project_url = project_url.replace(" ", "%20")
        self.client.runner('svn co "{url}" "{path}"'.format(url=project_url, path=self.client.current_folder))
        self.client.run("create . user/channel")

        folder = self.client.client_cache.source(ConanFileReference.loads("lib/0.1@user/channel"))
        self.assertTrue(os.path.exists(os.path.join(folder, "mysub", "myfile.txt")))
        self.assertFalse(os.path.exists(os.path.join(folder, "mysub", "conanfile.py")))

    def test_auto_conanfile_no_root(self):
        """
        Conanfile is not in the root of the repo: https://github.com/conan-io/conan/issues/3465
        """
        curdir = self.client.current_folder
        conanfile = base_svn.format(url="auto", revision="auto")
        project_url, rev = self.create_project(files={"conan/conanfile.py": conanfile,
                                                      "myfile.txt": "My file is copied"})
        self.client.runner('svn co "{url}" "{path}"'.format(url=project_url,
                                                            path=self.client.current_folder))
        self.client.run("create conan/ user/channel")

        sources_dir = self.client.client_cache.scm_folder(self.reference)
        self.assertEquals(load(sources_dir), curdir.replace('\\', '/'))  # Root of git is 'curdir'

    def test_deleted_source_folder(self):
        # SVN will always retrieve from 'remote'
        pass

    def test_excluded_repo_fies(self):
        conanfile = base_svn.format(url="auto", revision="auto")
        conanfile = conanfile.replace("short_paths = True", "short_paths = False")
        project_url, rev = self.create_project(files={"myfile": "contents",
                                                      "ignored.pyc": "bin",  # SVN ignores pyc files by default: http://blogs.collab.net/subversion/repository-dictated-configuration-day-3-global-ignores
                                                      # ".gitignore": "*.pyc\n",
                                                      "myfile.txt": "My file!",
                                                      "conanfile.py": conanfile})
        project_url = project_url.replace(" ", "%20")
        self.client.runner('svn co "{url}" "{path}"'.format(url=project_url, path=self.client.current_folder))

        self.client.run("create . user/channel")
        self.assertIn("Copying sources to build folder", self.client.out)
        pref = PackageReference(ConanFileReference.loads("lib/0.1/user/channel"),
                                "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        bf = self.client.client_cache.build(pref)
        self.assertTrue(os.path.exists(os.path.join(bf, "myfile.txt")))
        self.assertTrue(os.path.exists(os.path.join(bf, "myfile")))
        self.assertTrue(os.path.exists(os.path.join(bf, ".svn")))
        self.assertFalse(os.path.exists(os.path.join(bf, "ignored.pyc")))

    def test_local_source(self):
        curdir = self.client.current_folder
        conanfile = base_svn.format(url="auto", revision="auto")
        conanfile += """
    def source(self):
        self.output.warn("SOURCE METHOD CALLED")
"""
        project_url, rev = self.create_project(files={"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        project_url = project_url.replace(" ", "%20")
        self.client.runner('svn co "{url}" "{path}"'.format(url=project_url, path=self.client.current_folder))
        self.client.save({"aditional_file.txt": "contents"})

        self.client.run("source . --source-folder=./source")
        self.assertTrue(os.path.exists(os.path.join(curdir, "source", "myfile.txt")))
        self.assertIn("SOURCE METHOD CALLED", self.client.out)
        # Even the not commited files are copied
        self.assertTrue(os.path.exists(os.path.join(curdir, "source", "aditional_file.txt")))
        self.assertIn("Getting sources from folder: %s" % curdir, self.client.out)

        # Export again but now with absolute reference, so no pointer file is created nor kept
        svn = SVN(curdir.replace("\\", "/"))
        conanfile = base_svn.format(url=svn.get_remote_url(), revision=svn.get_revision())
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
        self.assertIn("Getting sources from url: '{}'".format(project_url).lower(),
                      str(self.client.out).lower())
        self.assertIn("SOURCE METHOD CALLED", self.client.out)

    def test_local_source_subfolder(self):
        curdir = self.client.current_folder
        conanfile = base_svn.replace('"revision": "{revision}"',
                                     '"revision": "{revision}",\n        '
                                     '"subfolder": "mysub"')
        conanfile = conanfile.format(url="auto", revision="auto")
        conanfile += """
    def source(self):
        self.output.warn("SOURCE METHOD CALLED")
"""
        project_url, rev = self.create_project(files={"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        project_url = project_url.replace(" ", "%20")
        self.client.runner('svn co "{url}" "{path}"'.format(url=project_url, path=self.client.current_folder))

        self.client.run("source . --source-folder=./source")
        self.assertFalse(os.path.exists(os.path.join(curdir, "source", "myfile.txt")))
        self.assertTrue(os.path.exists(os.path.join(curdir, "source", "mysub", "myfile.txt")))
        self.assertIn("SOURCE METHOD CALLED", self.client.out)

    def test_install_checked_out(self):
        test_server = TestServer()
        self.servers = {"myremote": test_server}
        self.client = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})

        curdir = self.client.current_folder.replace("\\", "/")
        conanfile = base_svn.format(url="auto", revision="auto")
        project_url, rev = self.create_project(files={"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        project_url = project_url.replace(" ", "%20")
        self.client.runner('svn co "{url}" "{path}"'.format(url=project_url, path=self.client.current_folder))
        self.client.run("export . lasote/channel")
        self.client.run("upload lib* -c")

        # Take other client, the old client folder will be used as a remote
        client2 = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})
        client2.run("install lib/0.1@lasote/channel --build")
        self.assertIn("My file is copied", client2.out)

    def test_source_removed_in_local_cache(self):
        conanfile = '''
from conans import ConanFile, tools

class ConanLib(ConanFile):
    scm = {
        "type": "svn",
        "url": "auto",
        "revision": "auto",
    }

    def build(self):
        contents = tools.load("myfile")
        self.output.warn("Contents: %s" % contents)

'''
        project_url, rev = self.create_project(files={"myfile": "contents", "conanfile.py": conanfile})
        project_url = project_url.replace(" ", "%20")
        self.client.runner('svn co "{url}" "{path}"'.format(url=project_url, path=self.client.current_folder))

        self.client.run("create . lib/1.0@user/channel")
        self.assertIn("Contents: contents", self.client.out)
        self.client.save({"myfile": "Contents 2"})
        self.client.run("create . lib/1.0@user/channel")
        self.assertIn("Contents: Contents 2", self.client.out)
        self.assertIn("Detected 'scm' auto in conanfile, trying to remove source folder",
                      self.client.out)

    def test_submodule(self):
        # SVN has no submodules, may add something related to svn:external?
        pass

    def test_source_method_export_sources_and_scm_mixed(self):
        project_url, rev = self.create_project(files={"myfile": "contents"})
        project_url = project_url.replace(" ", "%20")
        self.client.runner('svn co "{url}" "{path}"'.format(url=project_url, path=self.client.current_folder))

        conanfile = '''
import os
from conans import ConanFile, tools

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    exports_sources = "file.txt"
    scm = {{
        "type": "svn",
        "url": "{url}",
        "revision": "{rev}",
        "subfolder": "src"
    }}

    def source(self):
        self.output.warn("SOURCE METHOD CALLED")
        assert(os.path.exists("file.txt"))
        assert(os.path.exists(os.path.join("src", "myfile")))
        tools.save("cosa.txt", "contents")

    def build(self):
        assert(os.path.exists("file.txt"))
        assert(os.path.exists("cosa.txt"))
        self.output.warn("BUILD METHOD CALLED")
'''.format(url=project_url, rev=rev)
        self.client.save({"conanfile.py": conanfile, "file.txt": "My file is copied"})
        self.client.run("create . user/channel")
        self.assertIn("SOURCE METHOD CALLED", self.client.out)
        self.assertIn("BUILD METHOD CALLED", self.client.out)

    def test_scm_serialization(self):
        data = {"url": "myurl", "revision": "23", "username": "myusername",
                "password": "mypassword", "type": "svn", "verify_ssl": True,
                "subfolder": "mysubfolder"}
        conanfile = namedtuple("ConanfileMock", "scm")(data)
        scm_data = SCMData(conanfile)
        the_json = str(scm_data)
        data2 = json.loads(the_json)
        self.assertEquals(data, data2)
