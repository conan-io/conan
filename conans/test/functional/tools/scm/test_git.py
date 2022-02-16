import textwrap

from conans.test.utils.scm import create_local_git_repo, git_change_and_commit, git_create_bare_repo
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


class TestBasicCaptureExportGit:
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
            new_commit = git_change_and_commit({"conanfile.py": self.conanfile + "\n# some coment!"},
                                               c.current_folder)

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


class TestCaptureExportGitSCM:
    """ test the get_url_commit() high level method intended for SCM capturing into conandata.yaml
    """
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.scm import Git

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def export(self):
                git = Git(self, self.recipe_folder)
                scm_url, scm_commit = git.get_url_commit()
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
        assert "pkg/0.1: SCM COMMIT: {}".format(commit) in c.out
        assert "pkg/0.1: SCM URL: {}".format(c.current_folder) in c.out

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
            new_commit = git_change_and_commit({"conanfile.py": self.conanfile + "\n# some coment!"},
                                               c.current_folder)

            c.run("export .")
            assert "pkg/0.1: SCM COMMIT: {}".format(new_commit) in c.out
            # NOTE: commit not pushed yet, so locally is the current folder
            assert "pkg/0.1: SCM URL: {}".format(c.current_folder) in c.out
            c.run_command("git push")
            c.run("export .")
            assert "pkg/0.1: SCM COMMIT: {}".format(new_commit) in c.out
            assert "pkg/0.1: SCM URL: {}".format(url) in c.out
