import os
import textwrap
import unittest
from collections import namedtuple

import pytest
from parameterized.parameterized import parameterized

from conans.client.tools.scm import Git, SVN
from conans.client.tools.win import get_cased_path
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.scm import SCMData
from conans.test.utils.scm import create_local_git_repo, SVNLocalRepoTestCase
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, GenConanfile
from conans.util.files import load, rmdir, save, to_file_bytes
from conans.test.utils.tools import TestClient, TestServer, TurboTestClient


base = '''
import os
from conans import ConanFile, tools

def get_svn_remote(path_from_conanfile):
    svn = tools.SVN(os.path.join(os.path.dirname(__file__), path_from_conanfile))
    return svn.get_remote_url()

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    short_paths = True
    scm = {{
        "type": "%s",
        "url": {url},
        "revision": "{revision}",
    }}

    def build(self):
        sf = self.scm.get("subfolder")
        path = os.path.join(sf, "myfile.txt") if sf else "myfile.txt"
        self.output.warn(tools.load(path))
'''

base_git = base % "git"
base_svn = base % "svn"


def _quoted(item):
    return '"{}"'.format(item)


@pytest.mark.tool_git
class GitSCMTest(unittest.TestCase):

    def setUp(self):
        self.ref = ConanFileReference.loads("lib/0.1@user/channel")
        self.client = TestClient()

    def _commit_contents(self):
        self.client.run_command("git init .")
        self.client.run_command('git config user.email "you@example.com"')
        self.client.run_command('git config user.name "Your Name"')
        self.client.run_command("git add .")
        self.client.run_command('git commit -m  "commiting"')

    def test_scm_other_type_ignored(self):
        conanfile = '''
from conans import ConanFile, tools

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    scm = ["Other stuff"]

    def build(self):
        self.output.writeln("scm: {}".format(self.scm))
'''
        self.client.save({"conanfile.py": conanfile})
        # nothing breaks
        self.client.run("create . user/channel")
        self.assertIn("['Other stuff']", self.client.out)

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
        folder = self.client.cache.package_layout(self.ref).source()
        self.assertIn("othersubfolder", os.listdir(folder))
        self.assertTrue(os.path.exists(os.path.join(folder, "othersubfolder", "myfile")))

    def test_auto_filesystem_remote_git(self):
        # https://github.com/conan-io/conan/issues/3109
        conanfile = base_git.format(directory="None", url=_quoted("auto"), revision="auto")
        repo = temp_folder()
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"}, repo)
        with self.client.chdir(repo):
            self.client.run_command("git init .")
            self.client.run_command('git config user.email "you@example.com"')
            self.client.run_command('git config user.name "Your Name"')
            self.client.run_command("git add .")
            self.client.run_command('git commit -m  "commiting"')
        self.client.run_command('git clone "%s" .' % repo)
        self.client.run("export . user/channel")
        self.assertIn("WARN: Repo origin looks like a local path", self.client.out)
        self.client.run("remove lib/0.1* -s -f")  # Remove the source folder, it will get from url
        self.client.run("install lib/0.1@user/channel --build")
        self.assertIn("lib/0.1@user/channel: SCM: Getting sources from url:", self.client.out)

    def test_auto_git(self):
        curdir = get_cased_path(self.client.current_folder).replace("\\", "/")
        conanfile = base_git.format(directory="None", url=_quoted("auto"), revision="auto")
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self.client.init_git_repo()
        self.client.run("export . user/channel")
        self.assertIn("WARN: Repo origin cannot be deduced, 'auto' fields won't be replaced",
                      self.client.out)

        self.client.run_command('git remote add origin https://myrepo.com.git')

        # Create the package, will copy the sources from the local folder
        self.client.run("create . user/channel")
        self.assertIn("Repo origin deduced by 'auto': https://myrepo.com.git", self.client.out)
        self.assertIn("Revision deduced by 'auto'", self.client.out)
        self.assertIn("SCM: Getting sources from folder: %s" % curdir, self.client.out)
        self.assertIn("My file is copied", self.client.out)

        # check blank lines are respected in replacement
        self.client.run("get lib/0.1@user/channel")
        self.assertIn("""}

    def build(self):""", self.client.out)

        # Export again but now with absolute reference, so no sources are copied from the local dir
        git = Git(curdir)
        self.client.save({"conanfile.py": base_git.format(url=_quoted(curdir),
                                                          revision=git.get_revision())})
        self.client.run("create . user/channel")
        self.assertNotIn("Repo origin deduced by 'auto'", self.client.out)
        self.assertNotIn("Revision deduced by 'auto'", self.client.out)
        self.assertNotIn("Getting sources from folder: %s" % curdir, self.client.out)
        self.assertIn("SCM: Getting sources from url: '%s'" % curdir, self.client.out)
        self.assertIn("My file is copied", self.client.out)

    def test_auto_subfolder(self):
        conanfile = base_git.replace('"revision": "{revision}"',
                                     '"revision": "{revision}",\n        '
                                     '"subfolder": "mysub"')
        conanfile = conanfile.replace("short_paths = True", "short_paths = False")
        conanfile = conanfile.format(directory="None", url=_quoted("auto"), revision="auto")
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self.client.init_git_repo()
        self.client.run_command('git remote add origin https://myrepo.com.git')
        self.client.run("create . user/channel")

        ref = ConanFileReference.loads("lib/0.1@user/channel")
        folder = self.client.cache.package_layout(ref).source()
        self.assertTrue(os.path.exists(os.path.join(folder, "mysub", "myfile.txt")))
        self.assertFalse(os.path.exists(os.path.join(folder, "mysub", "conanfile.py")))

    def test_ignore_dirty_subfolder(self):
        # https://github.com/conan-io/conan/issues/6070
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, tools

            class ConanLib(ConanFile):
                name = "lib"
                version = "0.1"
                short_paths = True
                scm = {
                    "type": "git",
                    "url": "auto",
                    "revision": "auto",
                }

                def build(self):
                    path = os.path.join("base_file.txt")
                    assert os.path.exists(path)
        """)
        self.client.save({"test/main/conanfile.py": conanfile, "base_file.txt": "foo"})
        self.client.init_git_repo()
        self.client.run_command('git remote add origin https://myrepo.com.git')

        # Introduce changes
        self.client.save({"dirty_file.txt": "foo"})
        # The build() method will verify that the files from the repository are copied ok
        self.client.run("create test/main/conanfile.py user/channel")
        self.assertIn("Package '{}' created".format(NO_SETTINGS_PACKAGE_ID), self.client.out)

    def test_auto_conanfile_no_root(self):
        """
        Conanfile is not in the root of the repo: https://github.com/conan-io/conan/issues/3465
        """
        conanfile = base_git.format(url=_quoted("auto"), revision="auto")
        self.client.save({"conan/conanfile.py": conanfile, "myfile.txt": "content of my file"})
        self._commit_contents()
        self.client.run_command('git remote add origin https://myrepo.com.git')

        # Create the package
        self.client.run("create conan/ user/channel")

        # Check that the conanfile is on the source/conan
        ref = ConanFileReference.loads("lib/0.1@user/channel")
        source_folder = self.client.cache.package_layout(ref).source()
        self.assertTrue(os.path.exists(os.path.join(source_folder, "conan", "conanfile.py")))

    def test_deleted_source_folder(self):
        path, _ = create_local_git_repo({"myfile": "contents"}, branch="my_release")
        conanfile = base_git.format(url=_quoted("auto"), revision="auto")
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self.client.init_git_repo(main_branch="main")
        self.client.run_command('git remote add origin "%s"' % path.replace("\\", "/"))
        self.client.run_command('git push origin main')
        self.client.run("export . user/channel")

        # delete old source, but it doesn't matter because the sources are in the cache
        rmdir(self.client.current_folder)
        new_curdir = temp_folder()
        self.client.current_folder = new_curdir

        self.client.run("install lib/0.1@user/channel --build")
        self.assertNotIn("Getting sources from url: '%s'" % path.replace("\\", "/"),
                         self.client.out)

        # If the remove the source folder, then it is fetched from the "remote" doing an install
        self.client.run("remove lib/0.1@user/channel -f -s")
        self.client.run("install lib/0.1@user/channel --build")
        self.assertIn("SCM: Getting sources from url: '%s'" % path.replace("\\", "/"),
                      self.client.out)

    def test_excluded_repo_files(self):
        conanfile = base_git.format(url=_quoted("auto"), revision="auto")
        conanfile = conanfile.replace("short_paths = True", "short_paths = False")
        gitignore = textwrap.dedent("""
            *.pyc
            my_excluded_folder
            other_folder/excluded_subfolder
            """)
        self.client.init_git_repo({"myfile": "contents",
                                   "ignored.pyc": "bin",
                                   ".gitignore": gitignore,
                                   "myfile.txt": "My file!",
                                   "my_excluded_folder/some_file": "hey Apple!",
                                   "other_folder/excluded_subfolder/some_file": "hey Apple!",
                                   "other_folder/valid_file": "!",
                                   "conanfile.py": conanfile},
                                  branch="my_release")

        self.client.run("create . user/channel")
        self.assertIn("Copying sources to build folder", self.client.out)
        pref = PackageReference(ConanFileReference.loads("lib/0.1@user/channel"),
                                NO_SETTINGS_PACKAGE_ID)
        bf = self.client.cache.package_layout(pref.ref).build(pref)
        self.assertTrue(os.path.exists(os.path.join(bf, "myfile.txt")))
        self.assertTrue(os.path.exists(os.path.join(bf, "myfile")))
        self.assertTrue(os.path.exists(os.path.join(bf, ".git")))
        self.assertFalse(os.path.exists(os.path.join(bf, "ignored.pyc")))
        self.assertFalse(os.path.exists(os.path.join(bf, "my_excluded_folder")))
        self.assertTrue(os.path.exists(os.path.join(bf, "other_folder", "valid_file")))
        self.assertFalse(os.path.exists(os.path.join(bf, "other_folder", "excluded_subfolder")))

    def test_local_source(self):
        curdir = self.client.current_folder.replace("\\", "/")
        conanfile = base_git.format(url=_quoted("auto"), revision="auto")
        conanfile += """
    def source(self):
        self.output.warn("SOURCE METHOD CALLED")
"""
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self.client.init_git_repo()
        self.client.save({"aditional_file.txt": "contents"})

        self.client.run("source . --source-folder=./source")
        self.assertTrue(os.path.exists(os.path.join(curdir, "source", "myfile.txt")))
        self.assertIn("SOURCE METHOD CALLED", self.client.out)
        # Even the not commited files are copied
        self.assertTrue(os.path.exists(os.path.join(curdir, "source", "aditional_file.txt")))
        self.assertIn("SCM: Getting sources from folder: %s" % curdir,
                      str(self.client.out).replace("\\", "/"))

        # Export again but now with absolute reference, so no pointer file is created nor kept
        git = Git(curdir.replace("\\", "/"))
        conanfile = base_git.format(url=_quoted(curdir.replace("\\", "/")),
                                    revision=git.get_revision())
        conanfile += """
    def source(self):
        self.output.warn("SOURCE METHOD CALLED")
"""
        self.client.save({"conanfile.py": conanfile,
                          "myfile2.txt": "My file is copied"})
        self.client.run("source . --source-folder=./source2")
        # myfile2 is no in the specified commit
        self.assertFalse(os.path.exists(os.path.join(curdir, "source2", "myfile2.txt")))
        self.assertTrue(os.path.exists(os.path.join(curdir, "source2", "myfile.txt")))
        self.assertIn("SCM: Getting sources from url: '%s'" % curdir.replace("\\", "/"),
                      self.client.out)
        self.assertIn("SOURCE METHOD CALLED", self.client.out)

    def test_local_source_subfolder(self):
        curdir = self.client.current_folder
        conanfile = base_git.replace('"revision": "{revision}"',
                                     '"revision": "{revision}",\n        '
                                     '"subfolder": "mysub"')
        conanfile = conanfile.format(url=_quoted("auto"), revision="auto")
        conanfile += """
    def source(self):
        self.output.warn("SOURCE METHOD CALLED")
"""
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self.client.init_git_repo()

        self.client.run("source . --source-folder=./source")
        self.assertFalse(os.path.exists(os.path.join(curdir, "source", "myfile.txt")))
        self.assertTrue(os.path.exists(os.path.join(curdir, "source", "mysub", "myfile.txt")))
        self.assertIn("SOURCE METHOD CALLED", self.client.out)

    @parameterized.expand([
        ("local", "v1.0", True),
        ("local", None, False),
        ("https://github.com/conan-io/conan.git", "0.22.1", True),
        ("https://github.com/conan-io/conan.git", "c6cc15fa2f4b576bd70c9df11942e61e5cc7d746", False)])
    def test_shallow_clone_remote(self, remote, revision, is_tag):
        # https://github.com/conan-io/conan/issues/5570
        self.client = TestClient()

        # "remote" git
        if remote == "local":
            remote, rev = create_local_git_repo(tags=[revision] if is_tag else None,
                                                files={"conans/model/username.py": "foo"})
            if revision is None:  # Get the generated commit
                revision = rev

        # Use explicit URL to avoid local optimization (scm_folder.txt)
        conanfile = '''
import os
from conans import ConanFile, tools

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    scm = {"type": "git", "url": "%s", "revision": "%s"}

    def build(self):
        assert os.path.exists(os.path.join(self.build_folder, "conans", "model", "username.py"))
''' % (remote, revision)
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . user/channel")

    def test_install_checked_out(self):
        test_server = TestServer()
        self.servers = {"myremote": test_server}
        self.client = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})

        curdir = self.client.current_folder.replace("\\", "/")
        conanfile = base_git.format(url=_quoted("auto"), revision="auto")
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self.client.init_git_repo()
        cmd = 'git remote add origin "%s"' % curdir
        self.client.run_command(cmd)
        self.client.run("export . lasote/channel")
        self.client.run("upload lib* -c")

        # Take other client, the old client folder will be used as a remote
        client2 = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})
        client2.run("install lib/0.1@lasote/channel --build")
        self.assertIn("My file is copied", client2.out)

    def test_source_removed_in_local_cache(self):
        conanfile = textwrap.dedent('''
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
            ''')

        self.client.init_git_repo({"myfile": "contents", "conanfile.py": conanfile},
                                  branch="my_release", origin_url="https://myrepo.com.git")
        self.client.run("create . lib/1.0@user/channel")
        self.assertIn("Contents: contents", self.client.out)
        self.client.save({"myfile": "Contents 2"})
        self.client.run("create . lib/1.0@user/channel")
        self.assertIn("Contents: Contents 2", self.client.out)

    def test_submodule(self):
        subsubmodule, _ = create_local_git_repo({"subsubmodule": "contents"})
        submodule, _ = create_local_git_repo({"submodule": "contents"}, submodules=[subsubmodule])
        path, commit = create_local_git_repo({"myfile": "contents"}, branch="my_release",
                                             submodules=[submodule])

        def _relative_paths(folder_):
            sub_path = os.path.join(folder_, os.path.basename(os.path.normpath(submodule)))
            subsub_path = os.path.join(sub_path, os.path.basename(os.path.normpath(subsubmodule)))
            return sub_path, subsub_path

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

        ref = ConanFileReference.loads("lib/0.1@user/channel")
        folder = self.client.cache.package_layout(ref).source()
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

        self.client.run("create . user/channel", assert_error=True)
        self.assertIn("Invalid 'submodule' attribute value in the 'scm'.",
                      self.client.out)

        # Check shallow
        conanfile = tmp.format(url=path, revision=commit, submodule="shallow")
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . user/channel")

        ref = ConanFileReference.loads("lib/0.1@user/channel")
        folder = self.client.cache.package_layout(ref).source()
        submodule_path, subsubmodule_path = _relative_paths(folder)
        self.assertTrue(os.path.exists(os.path.join(folder, "myfile")))
        self.assertTrue(os.path.exists(os.path.join(submodule_path, "submodule")))
        self.assertFalse(os.path.exists(os.path.join(subsubmodule_path, "subsubmodule")))

        # Check recursive
        conanfile = tmp.format(url=path, revision=commit, submodule="recursive")
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . user/channel")

        ref = ConanFileReference.loads("lib/0.1@user/channel")
        folder = self.client.cache.package_layout(ref).source()
        submodule_path, subsubmodule_path = _relative_paths(folder)
        self.assertTrue(os.path.exists(os.path.join(folder, "myfile")))
        self.assertTrue(os.path.exists(os.path.join(submodule_path, "submodule")))
        self.assertTrue(os.path.exists(os.path.join(subsubmodule_path, "subsubmodule")))

    def test_scm_bad_filename(self):
        # Fixes: #3500
        badfilename = "\xE3\x81\x82badfile.txt"
        path, _ = create_local_git_repo({"goodfile.txt": "good contents"}, branch="my_release")
        save(to_file_bytes(os.path.join(self.client.current_folder, badfilename)), "contents")
        self.client.run_command('git remote add origin "%s"' % path.replace("\\", "/"), cwd=path)

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
        path, _ = create_local_git_repo({"myfile": "contents"}, branch="my_release")

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
        "subfolder": "src/nested"
    }

    def source(self):
        self.output.warn("SOURCE METHOD CALLED")
        assert(os.path.exists("file.txt"))
        assert(os.path.exists(os.path.join("src", "nested", "myfile")))
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

    def test_scm_serialization(self):
        data = {"url": "myurl", "revision": "myrevision", "username": "myusername",
                "password": "mypassword", "type": "git", "verify_ssl": True,
                "subfolder": "mysubfolder"}
        conanfile = namedtuple("ConanfileMock", "scm")(data)
        scm_data = SCMData(conanfile)

        expected_output = '{"password": "mypassword", "revision": "myrevision",' \
                          ' "subfolder": "mysubfolder", "type": "git", "url": "myurl",' \
                          ' "username": "myusername"}'
        self.assertEqual(str(scm_data), expected_output)

    def test_git_delegated_function(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile
            from conans.client.tools.scm import Git

            def get_revision():
                here = os.path.dirname(__file__)
                git = Git(here)
                return git.get_commit()

            def get_url():
                def nested_url():
                    here = os.path.dirname(__file__)
                    git = Git(here)
                    return git.get_remote_url()
                return nested_url()

            class MyLib(ConanFile):
                name = "issue"
                version = "3831"
                scm = {'type': 'git', 'url': get_url(), 'revision': get_revision()}
            """)
        commit = self.client.init_git_repo({"conanfile.py": conanfile})

        self.client.run("export . user/channel")
        ref = ConanFileReference.loads("issue/3831@user/channel")
        exported_conanfile = self.client.cache.package_layout(ref).conanfile()
        content = load(exported_conanfile)
        self.assertIn(commit, content)

    def test_delegated_python_code(self):
        client = TestClient()
        code_file = textwrap.dedent("""
            from conans.tools import Git
            from conans import ConanFile

            def get_commit(repo_path):
                git = Git(repo_path)
                return git.get_commit()

            class MyLib(ConanFile):
                pass
            """)
        client.save({"conanfile.py": code_file})
        client.run("export . tool/0.1@user/testing")

        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, python_requires
            from conans.tools import load
            tool = python_requires("tool/0.1@user/testing")

            class MyLib(ConanFile):
                scm = {'type': 'git', 'url': '%s',
                       'revision': tool.get_commit(os.path.dirname(__file__))}
                def build(self):
                    self.output.info("File: {}".format(load("file.txt")))
            """ % client.current_folder.replace("\\", "/"))

        commit = client.init_git_repo({"conanfile.py": conanfile, "file.txt": "hello!"})
        client.run("export . pkg/0.1@user/channel")
        ref = ConanFileReference.loads("pkg/0.1@user/channel")
        exported_conanfile = client.cache.package_layout(ref).conanfile()
        content = load(exported_conanfile)
        self.assertIn(commit, content)

    def test_git_version(self):
        git = Git()
        self.assertNotIn("Error retrieving git", git.version)


@pytest.mark.tool_svn
class SVNSCMTest(SVNLocalRepoTestCase):

    def setUp(self):
        self.ref = ConanFileReference.loads("lib/0.1@user/channel")
        self.client = TestClient()

    def test_scm_other_type_ignored(self):
        conanfile = '''
from conans import ConanFile, tools

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    scm = ["Other stuff"]

    def build(self):
        self.output.writeln("scm: {}".format(self.scm))
'''
        self.client.save({"conanfile.py": conanfile})
        # nothing breaks
        self.client.run("create . user/channel")
        self.assertIn("['Other stuff']", self.client.out)

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
        ref = ConanFileReference.loads("lib/0.1@user/channel")
        folder = self.client.cache.package_layout(ref).source()
        self.assertIn("othersubfolder", os.listdir(folder))
        self.assertTrue(os.path.exists(os.path.join(folder, "othersubfolder", "myfile")))

    def test_auto_filesystem_remote_svn(self):
        # SVN origin will never be a local path (local repo has at least protocol file:///)
        pass

    def test_auto_svn(self):
        conanfile = base_svn.format(directory="None", url=_quoted("auto"), revision="auto")
        project_url, _ = self.create_project(files={"conanfile.py": conanfile,
                                                    "myfile.txt": "My file is copied"})
        project_url = project_url.replace(" ", "%20")
        self.client.run_command('svn co "{url}" "{path}"'.format(url=project_url,
                                                                 path=self.client.current_folder))

        curdir = self.client.current_folder.replace("\\", "/")
        # Create the package, will copy the sources from the local folder
        self.client.run("create . user/channel")
        self.assertIn("Repo origin deduced by 'auto': {}".format(project_url).lower(),
                      str(self.client.out).lower())
        self.assertIn("Revision deduced by 'auto'", self.client.out)
        self.assertIn("SCM: Getting sources from folder: %s" % curdir, self.client.out)
        self.assertIn("My file is copied", self.client.out)

        # Export again but now with absolute reference, so no pointer file is created nor kept
        svn = SVN(curdir)
        self.client.save({"conanfile.py": base_svn.format(url=_quoted(svn.get_remote_url()),
                                                          revision=svn.get_revision())})
        self.client.run("create . user/channel")
        self.assertNotIn("Repo origin deduced by 'auto'", self.client.out)
        self.assertNotIn("Revision deduced by 'auto'", self.client.out)
        self.assertIn("SCM: Getting sources from url: '{}'".format(project_url).lower(),
                      str(self.client.out).lower())
        self.assertIn("My file is copied", self.client.out)

    def test_auto_subfolder(self):
        conanfile = base_svn.replace('"revision": "{revision}"',
                                     '"revision": "{revision}",\n        '
                                     '"subfolder": "mysub"')
        conanfile = conanfile.replace("short_paths = True", "short_paths = False")
        conanfile = conanfile.format(directory="None", url=_quoted("auto"), revision="auto")

        project_url, _ = self.create_project(files={"conanfile.py": conanfile,
                                                    "myfile.txt": "My file is copied"})
        project_url = project_url.replace(" ", "%20")
        self.client.run_command('svn co "{url}" "{path}"'.format(url=project_url,
                                                                 path=self.client.current_folder))
        self.client.run("create . user/channel")

        ref = ConanFileReference.loads("lib/0.1@user/channel")
        folder = self.client.cache.package_layout(ref).source()
        self.assertTrue(os.path.exists(os.path.join(folder, "mysub", "myfile.txt")))
        self.assertFalse(os.path.exists(os.path.join(folder, "mysub", "conanfile.py")))

    def test_auto_conanfile_no_root(self):
        #  Conanfile is not in the root of the repo: https://github.com/conan-io/conan/issues/3465
        conanfile = base_svn.format(url="get_svn_remote('..')", revision="auto")
        project_url, _ = self.create_project(files={"conan/conanfile.py": conanfile,
                                                    "myfile.txt": "My file is copied"})
        self.client.run_command('svn co "{url}" "{path}"'.format(url=project_url,
                                                                 path=self.client.current_folder))
        self.client.run("create conan/ user/channel")

        # Check that the conanfile is on the source/conan
        ref = ConanFileReference.loads("lib/0.1@user/channel")
        source_folder = self.client.cache.package_layout(ref).source()
        self.assertTrue(os.path.exists(os.path.join(source_folder, "conan", "conanfile.py")))

    def test_deleted_source_folder(self):
        # SVN will always retrieve from 'remote'
        pass

    def test_excluded_repo_fies(self):
        conanfile = base_svn.format(url=_quoted("auto"), revision="auto")
        conanfile = conanfile.replace("short_paths = True", "short_paths = False")
        # SVN ignores pyc files by default:
        # http://blogs.collab.net/subversion/repository-dictated-configuration-day-3-global-ignores
        project_url, _ = self.create_project(files={"myfile": "contents",
                                                    "ignored.pyc": "bin",
                                                    # ".gitignore": "*.pyc\n",
                                                    "myfile.txt": "My file!",
                                                    "conanfile.py": conanfile})
        project_url = project_url.replace(" ", "%20")
        self.client.run_command('svn co "{url}" "{path}"'.format(url=project_url,
                                                                 path=self.client.current_folder))

        self.client.run("create . user/channel")
        self.assertIn("Copying sources to build folder", self.client.out)
        pref = PackageReference(ConanFileReference.loads("lib/0.1@user/channel"),
                                NO_SETTINGS_PACKAGE_ID)
        bf = self.client.cache.package_layout(pref.ref).build(pref)
        self.assertTrue(os.path.exists(os.path.join(bf, "myfile.txt")))
        self.assertTrue(os.path.exists(os.path.join(bf, "myfile")))
        self.assertTrue(os.path.exists(os.path.join(bf, ".svn")))
        self.assertFalse(os.path.exists(os.path.join(bf, "ignored.pyc")))

    def test_local_source(self):
        curdir = self.client.current_folder.replace("\\", "/")
        conanfile = base_svn.format(url=_quoted("auto"), revision="auto")
        conanfile += """
    def source(self):
        self.output.warn("SOURCE METHOD CALLED")
"""
        project_url, _ = self.create_project(files={"conanfile.py": conanfile,
                                                    "myfile.txt": "My file is copied"})
        project_url = project_url.replace(" ", "%20")
        self.client.run_command('svn co "{url}" "{path}"'.format(url=project_url,
                                                                 path=self.client.current_folder))
        self.client.save({"aditional_file.txt": "contents"})

        self.client.run("source . --source-folder=./source")
        self.assertTrue(os.path.exists(os.path.join(curdir, "source", "myfile.txt")))
        self.assertIn("SOURCE METHOD CALLED", self.client.out)
        # Even the not commited files are copied
        self.assertTrue(os.path.exists(os.path.join(curdir, "source", "aditional_file.txt")))
        self.assertIn("SCM: Getting sources from folder: %s" % curdir, self.client.out)

        # Export again but now with absolute reference, so no pointer file is created nor kept
        svn = SVN(curdir)
        conanfile = base_svn.format(url=_quoted(svn.get_remote_url()), revision=svn.get_revision())
        conanfile += """
    def source(self):
        self.output.warn("SOURCE METHOD CALLED")
"""
        self.client.save({"conanfile.py": conanfile,
                          "myfile2.txt": "My file is copied"})
        self.client.run_command("svn add myfile2.txt")
        self.client.run_command('svn commit -m  "commiting"')

        self.client.run("source . --source-folder=./source2")
        # myfile2 is no in the specified commit
        self.assertFalse(os.path.exists(os.path.join(curdir, "source2", "myfile2.txt")))
        self.assertTrue(os.path.exists(os.path.join(curdir, "source2", "myfile.txt")))
        self.assertIn("SCM: Getting sources from url: '{}'".format(project_url).lower(),
                      str(self.client.out).lower())
        self.assertIn("SOURCE METHOD CALLED", self.client.out)

    def test_local_source_subfolder(self):
        curdir = self.client.current_folder
        conanfile = base_svn.replace('"revision": "{revision}"',
                                     '"revision": "{revision}",\n        '
                                     '"subfolder": "mysub"')
        conanfile = conanfile.format(url=_quoted("auto"), revision="auto")
        conanfile += """
    def source(self):
        self.output.warn("SOURCE METHOD CALLED")
"""
        project_url, _ = self.create_project(files={"conanfile.py": conanfile,
                                                    "myfile.txt": "My file is copied"})
        project_url = project_url.replace(" ", "%20")
        self.client.run_command('svn co "{url}" "{path}"'.format(url=project_url,
                                                                 path=self.client.current_folder))

        self.client.run("source . --source-folder=./source")
        self.assertFalse(os.path.exists(os.path.join(curdir, "source", "myfile.txt")))
        self.assertTrue(os.path.exists(os.path.join(curdir, "source", "mysub", "myfile.txt")))
        self.assertIn("SOURCE METHOD CALLED", self.client.out)

    def test_install_checked_out(self):
        test_server = TestServer()
        self.servers = {"myremote": test_server}
        self.client = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})

        conanfile = base_svn.format(url=_quoted("auto"), revision="auto")
        project_url, _ = self.create_project(files={"conanfile.py": conanfile,
                                                    "myfile.txt": "My file is copied"})
        project_url = project_url.replace(" ", "%20")
        self.client.run_command('svn co "{url}" "{path}"'.format(url=project_url,
                                                                 path=self.client.current_folder))
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
        project_url, _ = self.create_project(files={"myfile": "contents",
                                                    "conanfile.py": conanfile})
        project_url = project_url.replace(" ", "%20")
        self.client.run_command('svn co "{url}" "{path}"'.format(url=project_url,
                                                                 path=self.client.current_folder))

        self.client.run("create . lib/1.0@user/channel")
        self.assertIn("Contents: contents", self.client.out)
        self.client.save({"myfile": "Contents 2"})
        self.client.run("create . lib/1.0@user/channel")
        self.assertIn("Contents: Contents 2", self.client.out)

    def test_submodule(self):
        # SVN has no submodules, may add something related to svn:external?
        pass

    def test_source_method_export_sources_and_scm_mixed(self):
        project_url, rev = self.create_project(files={"myfile": "contents"})
        project_url = project_url.replace(" ", "%20")
        self.client.run_command('svn co "{url}" "{path}"'.format(url=project_url,
                                                                 path=self.client.current_folder))

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

    def test_non_commited_changes_export(self):
        conanfile = base_git.format(revision="auto", url='"auto"')
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self.client.init_git_repo()
        self.client.run_command('git remote add origin https://myrepo.com.git')
        # Dirty file
        self.client.save({"dirty": "you dirty contents"})

        for command in ("export .", "create ."):
            self.client.run(command)
            self.assertIn("WARN: There are uncommitted changes, skipping the replacement "
                          "of 'scm.url' and 'scm.revision' auto fields. "
                          "Use --ignore-dirty to force it.", self.client.out)

            # We confirm that the replacement hasn't been done
            ref = ConanFileReference.loads("lib/0.1@")
            folder = self.client.cache.package_layout(ref).export()
            conanfile_contents = load(os.path.join(folder, "conanfile.py"))
            self.assertIn('"revision": "auto"', conanfile_contents)
            self.assertIn('"url": "auto"', conanfile_contents)

        # We repeat the export/create but now using the --ignore-dirty
        for command in ("export .", "create ."):
            self.client.run("{} --ignore-dirty".format(command))
            self.assertNotIn("WARN: There are uncommitted changes, skipping the replacement "
                             "of 'scm.url' and 'scm.revision' auto fields. "
                             "Use --ignore-dirty to force it.", self.client.out)
            # We confirm that the replacement has been done
            ref = ConanFileReference.loads("lib/0.1@")
            folder = self.client.cache.package_layout(ref).export()
            conanfile_contents = load(os.path.join(folder, "conanfile.py"))
            self.assertNotIn('"revision": "auto"', conanfile_contents)
            self.assertNotIn('"url": "auto"', conanfile_contents)

    def test_double_create(self):
        # https://github.com/conan-io/conan/issues/5195#issuecomment-551848955
        self.client = TestClient(default_server_user=True)
        conanfile = str(GenConanfile().
                        with_scm({"type": "git", "revision": "auto", "url": "auto"}).
                        with_import("import os").with_import("from conans import tools").
                        with_name("lib").
                        with_version("1.0"))
        conanfile += """
    def build(self):
        contents = tools.load("bla.sh")
        self.output.warn("Bla? {}".format(contents))
        """
        self.client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        self.client.init_git_repo()
        self.client.run_command('git remote add origin https://myrepo.com.git')
        #  modified blah.sh
        self.client.save({"bla.sh": "bla bla"})
        self.client.run("create . user/channel")
        self.assertIn("Bla? bla bla", self.client.out)
        #  modified blah.sh again
        self.client.save({"bla.sh": "bla2 bla2"})
        # Run conan create again
        self.client.run("create . user/channel")
        self.assertIn("Bla? bla2 bla2", self.client.out)


@pytest.mark.tool_svn
class SCMSVNWithLockedFilesTest(SVNLocalRepoTestCase):

    def test_propset_own(self):
        """ Apply svn:needs-lock property to every file in the own working-copy
        of the repository """

        conanfile = base_svn.format(directory="None", url=_quoted("auto"), revision="auto")
        project_url, _ = self.create_project(files={"conanfile.py": conanfile})
        project_url = project_url.replace(" ", "%20")

        # Add property needs-lock to my own copy
        client = TestClient()
        client.run_command('svn co "{url}" "{path}"'.format(url=project_url,
                                                            path=client.current_folder))

        for item in ['conanfile.py', ]:
            client.run_command('svn propset svn:needs-lock yes {}'.format(item))
        client.run_command('svn commit -m "lock some files"')

        client.run("export . user/channel")


@pytest.mark.tool_git
class SCMBlockUploadTest(unittest.TestCase):

    def test_upload_blocking_auto(self):
        client = TestClient(default_server_user=True)
        conanfile = base_git.format(revision="auto", url='"auto"')
        client.save({"conanfile.py": conanfile, "myfile.txt": "My file is copied"})
        create_local_git_repo(folder=client.current_folder)
        client.run_command('git remote add origin https://myrepo.com.git')
        # Dirty file
        client.save({"dirty": "you dirty contents"})
        client.run("create . user/channel")
        self.assertIn("WARN: There are uncommitted changes, skipping the replacement "
                      "of 'scm.url' and 'scm.revision' auto fields. "
                      "Use --ignore-dirty to force it.", client.out)
        # The upload has to fail, no "auto" fields are allowed
        client.run("upload lib/0.1@user/channel -r default", assert_error=True)
        self.assertIn("ERROR: lib/0.1@user/channel: Upload recipe to 'default' failed:"
                      " The recipe contains invalid data in the 'scm' attribute (some 'auto'"
                      " values or missing fields 'type', 'url' or 'revision'). Use '--force'"
                      " to ignore", client.out)
        # The upload with --force should work
        client.run("upload lib/0.1@user/channel -r default --force")
        self.assertIn("Uploading lib/0.1@user/channel to remote", client.out)

    def test_export_blocking_type_none(self):
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class ConanLib(ConanFile):
                scm = {
                    "type": None,
                    "url": "some url",
                    "revision": "some_rev",
                }
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . pkg/0.1@user/channel", assert_error=True)
        self.assertIn("ERROR: SCM not supported: None", client.out)

    def test_create_blocking_url_none(self):
        # If URL is None, it cannot create locally, as it will try to clone it
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class ConanLib(ConanFile):
                scm = {
                    "type": "git",
                    "url": None,
                    "revision": "some_rev",
                }
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/0.1@user/channel", assert_error=True)
        self.assertIn("Couldn't checkout SCM:", client.out)

    def test_upload_blocking_url_none_revision_auto(self):
        # if the revision is auto and the url is None, it can be created locally, but not uploaded
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class ConanLib(ConanFile):
                scm = {
                    "type": "git",
                    "url": None,
                    "revision": "auto",
                }
            """)
        client.save({"conanfile.py": conanfile})
        create_local_git_repo(folder=client.current_folder)
        client.run("create . pkg/0.1@user/channel")
        client.run("upload pkg/0.1@user/channel -r default", assert_error=True)
        self.assertIn("ERROR: pkg/0.1@user/channel: Upload recipe to 'default' failed: The recipe"
                      " contains invalid data in the 'scm' attribute (some 'auto' values or"
                      " missing fields 'type', 'url' or 'revision'). Use '--force' to ignore",
                      client.out)
        client.run("upload pkg/0.1@user/channel -r default --force")

    @pytest.mark.tool_git
    def test_scm_from_superclass(self):
        client = TurboTestClient()
        conanfile = '''from conans import ConanFile

def get_conanfile():

    class BaseConanFile(ConanFile):
        scm = {
            "type": "git",
            "url": "auto",
            "revision": "auto"
        }

    return BaseConanFile

class Baseline(ConanFile):
    name = "Base"
    version = "1.0.0"
'''
        client.init_git_repo({"conanfile.py": conanfile}, origin_url="http://whatever.com/c.git")
        client.run("export . conan/stable")
        conanfile1 = """from conans import ConanFile, python_requires, tools

baseline = "Base/1.0.0@conan/stable"

# recipe inherits properties from the conanfile defined in the baseline
class ModuleConan(python_requires(baseline).get_conanfile()):
    name = "module_name"
    version = "1.0.0"
"""
        conanfile2 = """from conans import ConanFile, python_requires, tools

baseline = "Base/1.0.0@conan/stable"

# recipe inherits properties from the conanfile defined in the baseline
class ModuleConan(python_requires(baseline).get_conanfile()):
    pass
"""

        for conanfile in [conanfile1, conanfile2]:
            client.save({"conanfile.py": conanfile})
            # Add and commit so it do the scm replacements correctly
            client.run_command("git add .")
            client.run_command('git commit -m  "commiting"')
            client.run("export . module_name/1.0.0@conan/stable")
            self.assertIn("module_name/1.0.0@conan/stable: "
                          "A new conanfile.py version was exported", client.out)
            ref = ConanFileReference.loads("module_name/1.0.0@conan/stable")
            contents = load(os.path.join(client.cache.package_layout(ref).export(),
                                         "conanfile.py"))
            class_str = 'class ModuleConan(python_requires(baseline).get_conanfile()):\n'
            self.assertIn('%s    scm = {"revision":' % class_str, contents)


class SCMUpload(unittest.TestCase):

    @pytest.mark.tool_git
    def test_scm_sources(self):
        """ Test conan_sources.tgz is deleted in server when removing 'exports_sources' and using
        'scm'"""
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):
    name = "test"
    version = "1.0"
"""
        exports_sources = """
    exports_sources = "include/*"
"""
        servers = {"upload_repo": TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                             users={"lasote": "mypass"})}
        client = TestClient(servers=servers, users={"upload_repo": [("lasote", "mypass")]})
        client.save({"conanfile.py": conanfile + exports_sources, "include/file": "content"})
        client.run("create . danimtb/testing")
        client.run("upload test/1.0@danimtb/testing -r upload_repo")
        self.assertIn("Uploading conan_sources.tgz", client.out)
        ref = ConanFileReference("test", "1.0", "danimtb", "testing")
        rev = servers["upload_repo"].server_store.get_last_revision(ref).revision
        ref = ref.copy_with_rev(rev)
        export_sources_path = os.path.join(servers["upload_repo"].server_store.export(ref),
                                           "conan_sources.tgz")
        self.assertTrue(os.path.exists(export_sources_path))

        scm = """
    scm = {"type": "git",
           "url": "auto",
           "revision": "auto"}
"""
        client.save({"conanfile.py": conanfile + scm})
        client.run_command("git init")
        client.run_command('git config user.email "you@example.com"')
        client.run_command('git config user.name "Your Name"')
        client.run_command("git remote add origin https://github.com/fake/fake.git")
        client.run_command("git add .")
        client.run_command("git commit -m \"initial commit\"")
        client.run("create . danimtb/testing")
        self.assertIn("Repo origin deduced by 'auto': https://github.com/fake/fake.git", client.out)
        client.run("upload test/1.0@danimtb/testing -r upload_repo")
        self.assertNotIn("Uploading conan_sources.tgz", client.out)
        rev = servers["upload_repo"].server_store.get_last_revision(ref).revision
        ref = ref.copy_with_rev(rev)
        export_sources_path = os.path.join(servers["upload_repo"].server_store.export(ref),
                                           "conan_sources.tgz")
        self.assertFalse(os.path.exists(export_sources_path))
