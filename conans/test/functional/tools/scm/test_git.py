import os
import re
import textwrap

import pytest
import six

from conans.test.utils.scm import create_local_git_repo, git_add_changes_commit, git_create_bare_repo
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import rmdir, save_files


@pytest.mark.skipif(six.PY2, reason="Only Py3")
class TestGitBasicCapture:
    """ base Git capture operations. They do not raise (unless errors)
    """
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.scm import Git

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def export(self):
                git = Git(self, self.recipe_folder)
                commit = git.get_commit()
                url = git.get_remote_url()
                self.output.info("URL: {}".format(url))
                self.output.info("COMMIT: {}".format(commit))
                in_remote = git.commit_in_remote(commit)
                self.output.info("COMMIT IN REMOTE: {}".format(in_remote))
                self.output.info("DIRTY: {}".format(git.is_dirty()))
        """)

    def test_capture_commit_local(self):
        """
        A local repo, without remote, will have commit, but no URL
        """
        c = TestClient()
        c.save({"conanfile.py": self.conanfile})
        commit = c.init_git_repo()
        c.run("export .")
        assert "pkg/0.1: COMMIT: {}".format(commit) in c.out
        assert "pkg/0.1: URL: None" in c.out
        assert "pkg/0.1: COMMIT IN REMOTE: False" in c.out
        assert "pkg/0.1: DIRTY: False" in c.out

    def test_capture_remote_url(self):
        """
        a cloned repo, will have a default "origin" remote and will manage to get URL
        """
        folder = temp_folder()
        url, commit = create_local_git_repo(files={"conanfile.py": self.conanfile}, folder=folder)

        c = TestClient()
        c.run_command('git clone "{}" myclone'.format(folder))
        with c.chdir("myclone"):
            c.run("export .")
            assert "pkg/0.1: COMMIT: {}".format(commit) in c.out
            assert "pkg/0.1: URL: {}".format(url) in c.out
            assert "pkg/0.1: COMMIT IN REMOTE: True" in c.out
            assert "pkg/0.1: DIRTY: False" in c.out

    def test_capture_remote_pushed_commit(self):
        """
        a cloned repo, after doing some new commit, no longer commit in remote, until push
        """
        url = git_create_bare_repo()

        c = TestClient()
        c.run_command('git clone "{}" myclone'.format(url))
        with c.chdir("myclone"):
            c.save({"conanfile.py": self.conanfile + "\n# some coment!"})
            new_commit = git_add_changes_commit(c.current_folder)

            c.run("export .")
            assert "pkg/0.1: COMMIT: {}".format(new_commit) in c.out
            assert "pkg/0.1: URL: {}".format(url) in c.out
            assert "pkg/0.1: COMMIT IN REMOTE: False" in c.out
            assert "pkg/0.1: DIRTY: False" in c.out
            c.run_command("git push")
            c.run("export .")
            assert "pkg/0.1: COMMIT: {}".format(new_commit) in c.out
            assert "pkg/0.1: URL: {}".format(url) in c.out
            assert "pkg/0.1: COMMIT IN REMOTE: True" in c.out
            assert "pkg/0.1: DIRTY: False" in c.out


@pytest.mark.skipif(six.PY2, reason="Only Py3")
class TestGitCaptureSCM:
    """ test the get_url_and_commit() high level method intended for SCM capturing
    into conandata.yaml
    """
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.scm import Git

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def export(self):
                git = Git(self, self.recipe_folder)
                scm_url, scm_commit = git.get_url_and_commit()
                self.output.info("SCM URL: {}".format(scm_url))
                self.output.info("SCM COMMIT: {}".format(scm_commit))
        """)

    def test_capture_commit_local(self):
        """
        A local repo, without remote, will provide its own URL to the export(),
        and if it has local changes, it will be marked as dirty, and raise an error
        """
        c = TestClient()
        c.save({"conanfile.py": self.conanfile})
        commit = c.init_git_repo()
        c.run("export .")
        assert "This revision will not be buildable in other computer" in c.out
        assert "pkg/0.1: SCM COMMIT: {}".format(commit) in c.out
        assert "pkg/0.1: SCM URL: {}".format(c.current_folder.replace("\\", "/")) in c.out

        c.save({"conanfile.py": self.conanfile + "\n# something...."})
        c.run("export .", assert_error=True)
        assert "Repo is dirty, cannot capture url and commit" in c.out

    def test_capture_remote_url(self):
        """
        a cloned repo that is expored, will report the URL of the remote
        """
        folder = temp_folder()
        url, commit = create_local_git_repo(files={"conanfile.py": self.conanfile}, folder=folder)

        c = TestClient()
        c.run_command('git clone "{}" myclone'.format(folder))
        with c.chdir("myclone"):
            c.run("export .")
            assert "pkg/0.1: SCM COMMIT: {}".format(commit) in c.out
            assert "pkg/0.1: SCM URL: {}".format(url) in c.out

    def test_capture_remote_pushed_commit(self):
        """
        a cloned repo, after doing some new commit, no longer commit in remote, until push
        """
        url = git_create_bare_repo()

        c = TestClient()
        c.run_command('git clone "{}" myclone'.format(url))
        with c.chdir("myclone"):
            c.save({"conanfile.py": self.conanfile + "\n# some coment!"})
            new_commit = git_add_changes_commit(c.current_folder)

            c.run("export .")
            assert "This revision will not be buildable in other computer" in c.out
            assert "pkg/0.1: SCM COMMIT: {}".format(new_commit) in c.out
            # NOTE: commit not pushed yet, so locally is the current folder
            assert "pkg/0.1: SCM URL: {}".format(c.current_folder.replace("\\", "/")) in c.out
            c.run_command("git push")
            c.run("export .")
            assert "pkg/0.1: SCM COMMIT: {}".format(new_commit) in c.out
            assert "pkg/0.1: SCM URL: {}".format(url) in c.out


@pytest.mark.skipif(six.PY2, reason="Only Py3")
class TestGitBasicClone:
    """ base Git cloning operations
    """
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.scm import Git
        from conan.tools.files import load

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def layout(self):
                self.folders.source = "source"

            def source(self):
                git = Git(self)
                git.clone(url="{url}", target=".")
                git.checkout(commit="{commit}")
                self.output.info("MYCMAKE: {{}}".format(load(self, "CMakeLists.txt")))
                self.output.info("MYFILE: {{}}".format(load(self, "src/myfile.h")))
        """)

    def test_clone_checkout(self):
        folder = os.path.join(temp_folder(), "myrepo")
        url, commit = create_local_git_repo(files={"src/myfile.h": "myheader!",
                                                   "CMakeLists.txt": "mycmake"}, folder=folder)
        # This second commit will NOT be used, as I will use the above commit in the conanfile
        save_files(path=folder, files={"src/myfile.h": "my2header2!"})
        git_add_changes_commit(folder=folder)

        c = TestClient()
        c.save({"conanfile.py": self.conanfile.format(url=url, commit=commit)})
        c.run("create .")
        assert "pkg/0.1: MYCMAKE: mycmake" in c.out
        assert "pkg/0.1: MYFILE: myheader!" in c.out

        # It also works in local flow
        c.run("source .")
        assert "conanfile.py (pkg/0.1): MYCMAKE: mycmake" in c.out
        assert "conanfile.py (pkg/0.1): MYFILE: myheader!" in c.out
        assert c.load("source/src/myfile.h") == "myheader!"
        assert c.load("source/CMakeLists.txt") == "mycmake"


class TestGitCloneWithArgs:
    """ Git cloning passing additional arguments
    """
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.scm import Git
        from conan.tools.files import load

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def layout(self):
                self.folders.source = "source"

            def source(self):
                git = Git(self)
                git.clone(url="{url}", target=".", args={args})
                self.output.info("MYCMAKE: {{}}".format(load(self, "CMakeLists.txt")))
                self.output.info("MYFILE: {{}}".format(load(self, "src/myfile.h")))
        """)

    def test_clone_specify_branch_or_tag(self):
        folder = os.path.join(temp_folder(), "myrepo")
        url, commit = create_local_git_repo(files={"src/myfile.h": "myheader!",
                                                   "CMakeLists.txt": "mycmake"}, folder=folder,
                                                   commits=3, branch="main", tags=["v1.2.3"])

        c = TestClient()
        git_args = ['--branch', 'main']
        c.save({"conanfile.py": self.conanfile.format(url=url, commit=commit, args=str(git_args))})
        c.run("create .")
        assert "pkg/0.1: MYCMAKE: mycmake" in c.out
        assert "pkg/0.1: MYFILE: myheader!" in c.out

        git_args = ['--branch', 'v1.2.3']
        c.save({"conanfile.py": self.conanfile.format(url=url, commit=commit, args=str(git_args))})
        c.run("create .")
        assert "pkg/0.1: MYCMAKE: mycmake" in c.out
        assert "pkg/0.1: MYFILE: myheader!" in c.out

    def test_clone_invalid_branch_argument(self):
        folder = os.path.join(temp_folder(), "myrepo")
        url, commit = create_local_git_repo(files={"src/myfile.h": "myheader!",
                                                   "CMakeLists.txt": "mycmake"}, folder=folder,
                                                   commits=3, branch="main", tags=["v1.2.3"])
        c = TestClient()
        git_args = ['--branch', 'foobar']
        c.save({"conanfile.py": self.conanfile.format(url=url, commit=commit, args=str(git_args))})
        with pytest.raises(Exception):
            c.run("create .")
            assert "Remote branch foobar not found" in c.out

@pytest.mark.skipif(six.PY2, reason="Only Py3")
class TestGitBasicSCMFlow:
    """ Build the full new SCM approach:
    - export() captures the URL and commit with get_url_and_commit(
    - export() stores it in conandata.yml
    - source() recovers the info from conandata.yml and clones it
    """
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.scm import Git
        from conan.tools.files import load, update_conandata

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def export(self):
                git = Git(self, self.recipe_folder)
                scm_url, scm_commit = git.get_url_and_commit()
                update_conandata(self, {"sources": {"commit": scm_commit, "url": scm_url}})

            def layout(self):
                self.folders.source = "."

            def source(self):
                git = Git(self)
                sources = self.conan_data["sources"]
                git.clone(url=sources["url"], target=".")
                git.checkout(commit=sources["commit"])
                self.output.info("MYCMAKE: {}".format(load(self, "CMakeLists.txt")))
                self.output.info("MYFILE: {}".format(load(self, "src/myfile.h")))

            def build(self):
                cmake = os.path.join(self.source_folder, "CMakeLists.txt")
                file_h = os.path.join(self.source_folder, "src/myfile.h")
                self.output.info("MYCMAKE-BUILD: {}".format(load(self, cmake)))
                self.output.info("MYFILE-BUILD: {}".format(load(self, file_h)))
        """)

    def test_full_scm(self):
        folder = os.path.join(temp_folder(), "myrepo")
        url, commit = create_local_git_repo(files={"conanfile.py": self.conanfile,
                                                   "src/myfile.h": "myheader!",
                                                   "CMakeLists.txt": "mycmake"}, folder=folder)

        c = TestClient(default_server_user=True)
        c.run_command('git clone "{}" .'.format(url))
        c.run("create .")
        assert "pkg/0.1: MYCMAKE: mycmake" in c.out
        assert "pkg/0.1: MYFILE: myheader!" in c.out
        c.run("upload * --all -c")

        # Do a change and commit, this commit will not be used by package
        save_files(path=folder, files={"src/myfile.h": "my2header2!"})
        git_add_changes_commit(folder=folder)

        # use another fresh client
        c2 = TestClient(servers=c.servers)
        c2.run("install pkg/0.1@ --build=pkg")
        assert "pkg/0.1: MYCMAKE: mycmake" in c2.out
        assert "pkg/0.1: MYFILE: myheader!" in c2.out

        # local flow
        c.run("install .")
        c.run("build .")
        assert "conanfile.py (pkg/0.1): MYCMAKE-BUILD: mycmake" in c.out
        assert "conanfile.py (pkg/0.1): MYFILE-BUILD: myheader!" in c.out

    def test_branch_flow(self):
        """ Testing that when a user creates a branch, and pushes a commit,
        the package can still be built from sources, and get_url_and_commit() captures the
        remote URL and not the local
        """
        url = git_create_bare_repo()
        c = TestClient(default_server_user=True)
        c.run_command('git clone "{}" .'.format(url))
        c.save({"conanfile.py": self.conanfile,
                "src/myfile.h": "myheader!",
                "CMakeLists.txt": "mycmake"})
        c.run_command("git checkout -b mybranch")
        git_add_changes_commit(folder=c.current_folder)
        c.run_command("git push --set-upstream origin mybranch")
        c.run("create .")
        assert "pkg/0.1: MYCMAKE: mycmake" in c.out
        assert "pkg/0.1: MYFILE: myheader!" in c.out
        c.run("upload * --all -c")
        rmdir(c.current_folder)  # Remove current folder to make sure things are not used from here

        # use another fresh client
        c2 = TestClient(servers=c.servers)
        c2.run("install pkg/0.1@ --build=pkg")
        assert "pkg/0.1: MYCMAKE: mycmake" in c2.out
        assert "pkg/0.1: MYFILE: myheader!" in c2.out


@pytest.mark.skipif(six.PY2, reason="Only Py3")
class TestGitBasicSCMFlowSubfolder:
    """ Same as above, but conanfile.py put in "conan" subfolder in the root
    """
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.scm import Git
        from conan.tools.files import load, update_conandata

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def export(self):
                git = Git(self, os.path.dirname(self.recipe_folder)) # PARENT!
                scm_url, scm_commit = git.get_url_and_commit()
                update_conandata(self, {"sources": {"commit": scm_commit, "url": scm_url}})

            def layout(self):
                self.folders.root = ".."
                self.folders.source = "."

            def source(self):
                git = Git(self)
                sources = self.conan_data["sources"]
                git.clone(url=sources["url"], target=".")
                git.checkout(commit=sources["commit"])
                self.output.info("MYCMAKE: {}".format(load(self, "CMakeLists.txt")))
                self.output.info("MYFILE: {}".format(load(self, "src/myfile.h")))

            def build(self):
                cmake = os.path.join(self.source_folder, "CMakeLists.txt")
                file_h = os.path.join(self.source_folder, "src/myfile.h")
                self.output.info("MYCMAKE-BUILD: {}".format(load(self, cmake)))
                self.output.info("MYFILE-BUILD: {}".format(load(self, file_h)))
        """)

    def test_full_scm(self):
        folder = os.path.join(temp_folder(), "myrepo")
        url, commit = create_local_git_repo(files={"conan/conanfile.py": self.conanfile,
                                                   "src/myfile.h": "myheader!",
                                                   "CMakeLists.txt": "mycmake"}, folder=folder)

        c = TestClient(default_server_user=True)
        c.run_command('git clone "{}" .'.format(url))
        c.run("create conan")
        assert "pkg/0.1: MYCMAKE: mycmake" in c.out
        assert "pkg/0.1: MYFILE: myheader!" in c.out
        c.run("upload * --all -c")

        # Do a change and commit, this commit will not be used by package
        save_files(path=folder, files={"src/myfile.h": "my2header2!"})
        git_add_changes_commit(folder=folder)

        # use another fresh client
        c2 = TestClient(servers=c.servers)
        c2.run("install pkg/0.1@ --build=pkg")
        assert "pkg/0.1: MYCMAKE: mycmake" in c2.out
        assert "pkg/0.1: MYFILE: myheader!" in c2.out

        # local flow
        c.run("install conan")
        c.run("build conan")
        assert "conanfile.py (pkg/0.1): MYCMAKE-BUILD: mycmake" in c.out
        assert "conanfile.py (pkg/0.1): MYFILE-BUILD: myheader!" in c.out


@pytest.mark.skipif(six.PY2, reason="Only Py3")
class TestGitMonorepoSCMFlow:
    """ Build the full new SCM approach:
    Same as above but with a monorepo with multiple subprojects
    """
    # TODO: swap_child_folder() not documented, not public usage
    conanfile = textwrap.dedent("""
        import os, shutil
        from conan import ConanFile
        from conan.tools.scm import Git
        from conan.tools.files import load, update_conandata
        from conan.tools.files.files import swap_child_folder

        class Pkg(ConanFile):
            name = "{pkg}"
            version = "0.1"

            {requires}

            def export(self):
                git = Git(self, self.recipe_folder)
                scm_url, scm_commit = git.get_url_and_commit()
                self.output.info("CAPTURING COMMIT: {{}}!!!".format(scm_commit))
                folder = os.path.basename(self.recipe_folder)
                update_conandata(self, {{"sources": {{"commit": scm_commit, "url": scm_url,
                                                      "folder": folder}}}})

            def layout(self):
                self.folders.source = "."

            def source(self):
                git = Git(self)
                sources = self.conan_data["sources"]
                git.clone(url=sources["url"], target=".")
                git.checkout(commit=sources["commit"])
                swap_child_folder(self.source_folder, sources["folder"])

            def build(self):
                cmake = os.path.join(self.source_folder, "CMakeLists.txt")
                file_h = os.path.join(self.source_folder, "src/myfile.h")
                self.output.info("MYCMAKE-BUILD: {{}}".format(load(self, cmake)))
                self.output.info("MYFILE-BUILD: {{}}".format(load(self, file_h)))
        """)

    def test_full_scm(self):
        folder = os.path.join(temp_folder(), "myrepo")
        conanfile1 = self.conanfile.format(pkg="pkg1", requires="")
        conanfile2 = self.conanfile.format(pkg="pkg2", requires="requires = 'pkg1/0.1'")
        url, commit = create_local_git_repo(files={"sub1/conanfile.py": conanfile1,
                                                   "sub1/src/myfile.h": "myheader1!",
                                                   "sub1/CMakeLists.txt": "mycmake1!",
                                                   "sub2/conanfile.py": conanfile2,
                                                   "sub2/src/myfile.h": "myheader2!",
                                                   "sub2/CMakeLists.txt": "mycmake2!"
                                                   },
                                            folder=folder)

        c = TestClient(default_server_user=True)
        c.run_command('git clone "{}" .'.format(url))
        c.run("create sub1")
        commit = re.search(r"CAPTURING COMMIT: (\S+)!!!", str(c.out)).group(1)
        assert "pkg1/0.1: MYCMAKE-BUILD: mycmake1!" in c.out
        assert "pkg1/0.1: MYFILE-BUILD: myheader1!" in c.out

        c.save({"sub2/src/myfile.h": "my2header!"})
        git_add_changes_commit(folder=c.current_folder)
        c.run("create sub2")
        assert "pkg2/0.1: MYCMAKE-BUILD: mycmake2!" in c.out
        assert "pkg2/0.1: MYFILE-BUILD: my2header!" in c.out

        # Exporting again sub1, gives us exactly the same revision as before
        c.run("export sub1")
        assert "CAPTURING COMMIT: {}".format(commit) in c.out
        c.run("upload * --all -c -r=default")

        # use another fresh client
        c2 = TestClient(servers=c.servers)
        c2.run("install pkg2/0.1@ --build")
        assert "pkg1/0.1: Checkout: {}".format(commit) in c2.out
        assert "pkg1/0.1: MYCMAKE-BUILD: mycmake1!" in c2.out
        assert "pkg1/0.1: MYFILE-BUILD: myheader1!" in c2.out
        assert "pkg2/0.1: MYCMAKE-BUILD: mycmake2!" in c2.out
        assert "pkg2/0.1: MYFILE-BUILD: my2header!" in c2.out


class TestConanFileSubfolder:
    """verify that we can have a conanfile in a subfolder
        # https://github.com/conan-io/conan/issues/11275
    """

    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.scm import Git
        from conan.tools.files import update_conandata, load

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def export(self):
                git = Git(self, os.path.dirname(self.recipe_folder))
                url, commit = git.get_url_and_commit()
                # We store the current url and commit in conandata.yml
                update_conandata(self, {"sources": {"commit": commit, "url": url}})
                self.output.info("URL: {}".format(url))
                self.output.info("COMMIT: {}".format(commit))

            def layout(self):
                pass # self.folders.source = "source"

            def source(self):
                git = Git(self)
                sources = self.conan_data["sources"]
                url = sources["url"]
                commit = sources["commit"]
                git.clone(url=url, target=".")
                git.checkout(commit=commit)
                self.output.info("MYCMAKE: {}".format(load(self, "CMakeLists.txt")))
                self.output.info("MYFILE: {}".format(load(self, "src/myfile.h")))
        """)

    def test_conanfile_subfolder(self):
        """
        A local repo, without remote, will have commit, but no URL
        """
        c = TestClient()
        c.save({"conan/conanfile.py": self.conanfile,
                "CMakeLists.txt": "mycmakelists",
                "src/myfile.h": "myheader"})
        commit = c.init_git_repo()
        c.run("export conan")
        assert "pkg/0.1: COMMIT: {}".format(commit) in c.out
        assert "pkg/0.1: URL: {}".format(c.current_folder.replace("\\", "/")) in c.out

        c.run("create conan")
        assert "pkg/0.1: MYCMAKE: mycmakelists" in c.out
        assert "pkg/0.1: MYFILE: myheader" in c.out
