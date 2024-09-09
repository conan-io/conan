import os
import platform
import re
import textwrap

import pytest

from conan.test.assets.cmake import gen_cmakelists
from conan.test.assets.sources import gen_function_cpp
from conan.test.utils.scm import create_local_git_repo, git_add_changes_commit, git_create_bare_repo
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conans.util.files import rmdir, save_files, save


@pytest.mark.tool("git")
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
                git = Git(self, self.recipe_folder, excluded=["myfile.txt", "mynew.txt"])
                commit = git.get_commit()
                repo_commit = git.get_commit(repository=True)
                url = git.get_remote_url()
                self.output.info("URL: {}".format(url))
                self.output.info("COMMIT: {}".format(commit))
                self.output.info("REPO_COMMIT: {}".format(repo_commit))
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
            assert "pkg/0.1: REPO_COMMIT: {}".format(commit) in c.out
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

    def test_capture_commit_local_subfolder(self):
        """
        A local repo, without remote, will have commit, but no URL, and sibling folders
        can be dirty, no prob
        """
        c = TestClient()
        c.save({"subfolder/conanfile.py": self.conanfile,
                "other/myfile.txt": "content"})
        commit = c.init_git_repo()
        c.save({"other/myfile.txt": "change content"})
        c.run("export subfolder")
        assert "pkg/0.1: COMMIT: {}".format(commit) in c.out
        assert "pkg/0.1: REPO_COMMIT: {}".format(commit) in c.out
        assert "pkg/0.1: URL: None" in c.out
        assert "pkg/0.1: COMMIT IN REMOTE: False" in c.out
        assert "pkg/0.1: DIRTY: False" in c.out
        commit2 = git_add_changes_commit(c.current_folder, msg="fix")
        c.run("export subfolder")
        assert "pkg/0.1: COMMIT: {}".format(commit) in c.out
        assert "pkg/0.1: REPO_COMMIT: {}".format(commit2) in c.out
        assert "pkg/0.1: URL: None" in c.out
        assert "pkg/0.1: COMMIT IN REMOTE: False" in c.out
        assert "pkg/0.1: DIRTY: False" in c.out

    def test_git_excluded(self):
        """
        A local repo, without remote, will have commit, but no URL
        """
        c = TestClient()
        c.save({"conanfile.py": self.conanfile,
                "myfile.txt": ""})
        c.init_git_repo()
        c.run("export . -vvv")
        assert "pkg/0.1: DIRTY: False" in c.out
        c.save({"myfile.txt": "changed",
                "mynew.txt": "new"})
        c.run("export .")
        assert "pkg/0.1: DIRTY: False" in c.out
        c.save({"other.txt": "new"})
        c.run("export .")
        assert "pkg/0.1: DIRTY: True" in c.out

        conf_excluded = f'core.scm:excluded+=["other.txt"]'
        save(c.cache.global_conf_path, conf_excluded)
        c.run("export .")
        assert "pkg/0.1: DIRTY: False" in c.out


@pytest.mark.tool("git")
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

    def test_capture_commit_local_repository(self):
        """
        same as above, but with ``get_url_and_commit(repository=True)``
        """
        c = TestClient()
        c.save({"pkg/conanfile.py": self.conanfile.replace("get_url_and_commit()",
                                                           "get_url_and_commit(repository=True)"),
                "somefile.txt": ""})
        commit = c.init_git_repo()
        c.run("export pkg")
        assert "This revision will not be buildable in other computer" in c.out
        assert "pkg/0.1: SCM COMMIT: {}".format(commit) in c.out
        assert "pkg/0.1: SCM URL: {}".format(c.current_folder.replace("\\", "/")) in c.out

        c.save({"somefile.txt": "something"})
        c.run("export pkg", assert_error=True)
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

    def test_capture_commit_modified_config(self):
        """
        A clean repo with the status.branch git config set to on
        Expected to not raise an error an return the commit and url
        """
        folder = temp_folder()
        url, commit = create_local_git_repo(files={"conanfile.py": self.conanfile}, folder=folder)
        c = TestClient()
        with c.chdir(folder):
            c.run_command("git config --local status.branch true")
            c.run("export .")
            assert "pkg/0.1: SCM COMMIT: {}".format(commit) in c.out
            assert "pkg/0.1: SCM URL: {}".format(url) in c.out

    def test_capture_commit_modified_config_untracked(self):
        """
        A dirty repo with the showUntrackedFiles git config set to off.
        Expected to throw an exception
        """
        folder = temp_folder()
        create_local_git_repo(files={"conanfile.py": self.conanfile}, folder=folder)
        c = TestClient()
        with c.chdir(folder):
            c.save(files={"some_header.h": "now the repo is dirty"})
            c.run_command("git config --local status.showUntrackedFiles no")
            c.run("export .", assert_error=True)
            assert "Repo is dirty, cannot capture url and commit" in c.out


@pytest.mark.tool("git")
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
        c.run("create . -v")
        # Clone is not printed, it might contain tokens
        assert 'pkg/0.1: RUN: git clone "<hidden>"  "."' in c.out
        assert "pkg/0.1: RUN: git checkout" in c.out
        assert "pkg/0.1: MYCMAKE: mycmake" in c.out
        assert "pkg/0.1: MYFILE: myheader!" in c.out

        # It also works in local flow
        c.run("source .")
        assert "conanfile.py (pkg/0.1): MYCMAKE: mycmake" in c.out
        assert "conanfile.py (pkg/0.1): MYFILE: myheader!" in c.out
        assert c.load("source/src/myfile.h") == "myheader!"
        assert c.load("source/CMakeLists.txt") == "mycmake"

    def test_clone_url_not_hidden(self):
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
                    git.clone(url="{url}", target=".", hide_url=False)
            """)
        folder = os.path.join(temp_folder(), "myrepo")
        url, _ = create_local_git_repo(files={"CMakeLists.txt": "mycmake"}, folder=folder)

        c = TestClient(light=True)
        c.save({"conanfile.py": conanfile.format(url=url)})
        c.run("create . -v")
        # Clone URL is explicitly printed
        assert f'pkg/0.1: RUN: git clone "{url}"  "."' in c.out

        # It also works in local flow
        c.run("source .")
        assert f'conanfile.py (pkg/0.1): RUN: git clone "{url}"  "."' in c.out

    def test_clone_target(self):
        # Clone to a different target folder
        # https://github.com/conan-io/conan/issues/14058
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
                    # Alternative, first defining the folder
                    # git = Git(self, "target")
                    # git.clone(url="{url}", target=".")
                    # git.checkout(commit="{commit}")

                    git = Git(self)
                    git.clone(url="{url}", target="tar get") # git clone url target
                    git.folder = "tar get"                   # cd target
                    git.checkout(commit="{commit}")         # git checkout commit

                    self.output.info("MYCMAKE: {{}}".format(load(self, "tar get/CMakeLists.txt")))
                    self.output.info("MYFILE: {{}}".format(load(self, "tar get/src/myfile.h")))
                """)
        folder = os.path.join(temp_folder(), "myrepo")
        url, commit = create_local_git_repo(files={"src/myfile.h": "myheader!",
                                                   "CMakeLists.txt": "mycmake"}, folder=folder)
        # This second commit will NOT be used, as I will use the above commit in the conanfile
        save_files(path=folder, files={"src/myfile.h": "my2header2!"})
        git_add_changes_commit(folder=folder)

        c = TestClient()
        c.save({"conanfile.py": conanfile.format(url=url, commit=commit)})
        c.run("create .")
        assert "pkg/0.1: MYCMAKE: mycmake" in c.out
        assert "pkg/0.1: MYFILE: myheader!" in c.out

    @pytest.mark.tool("msys2")
    def test_clone_msys2_win_bash(self):
        # To avoid regression in https://github.com/conan-io/conan/issues/14754
        folder = os.path.join(temp_folder(), "myrepo")
        url, commit = create_local_git_repo(files={"src/myfile.h": "myheader!",
                                                   "CMakeLists.txt": "mycmake"}, folder=folder)

        c = TestClient()
        conanfile_win_bash = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.scm import Git
            from conan.tools.files import load

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                win_bash = True

                def layout(self):
                    self.folders.source = "source"

                def source(self):
                    git = Git(self)
                    git.clone(url="{url}", target=".")
                    git.checkout(commit="{commit}")
                    self.output.info("MYCMAKE: {{}}".format(load(self, "CMakeLists.txt")))
                    self.output.info("MYFILE: {{}}".format(load(self, "src/myfile.h")))
            """)
        c.save({"conanfile.py": conanfile_win_bash.format(url=url, commit=commit)})
        conf = "-c tools.microsoft.bash:subsystem=msys2 -c tools.microsoft.bash:path=bash.exe"
        c.run(f"create . {conf}")
        assert "pkg/0.1: MYCMAKE: mycmake" in c.out
        assert "pkg/0.1: MYFILE: myheader!" in c.out

        # It also works in local flow, not running in msys2 at all
        c.run(f"source .")
        assert "conanfile.py (pkg/0.1): MYCMAKE: mycmake" in c.out
        assert "conanfile.py (pkg/0.1): MYFILE: myheader!" in c.out
        assert c.load("source/src/myfile.h") == "myheader!"
        assert c.load("source/CMakeLists.txt") == "mycmake"


@pytest.mark.tool("git")
class TestGitShallowClone:
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
                git.fetch_commit(url="{url}", commit="{commit}")
                self.output.info("MYCMAKE: {{}}".format(load(self, "CMakeLists.txt")))
                self.output.info("MYFILE: {{}}".format(load(self, "src/myfile.h")))
        """)

    @pytest.mark.skipif(platform.system() == "Linux", reason="Git version in Linux not support it")
    def test_clone_checkout(self):
        folder = os.path.join(temp_folder(), "myrepo")
        url, commit = create_local_git_repo(files={"src/myfile.h": "myheader!",
                                                   "CMakeLists.txt": "mycmake"}, folder=folder)
        # This second commit will NOT be used, as I will use the above commit in the conanfile
        save_files(path=folder, files={"src/myfile.h": "my2header2!"})
        git_add_changes_commit(folder=folder)

        c = TestClient()
        c.save({"conanfile.py": self.conanfile.format(url=url, commit=commit)})
        c.run("create . -v")
        assert 'pkg/0.1: RUN: git remote add origin "<hidden>"' in c.out
        assert "pkg/0.1: MYCMAKE: mycmake" in c.out
        assert "pkg/0.1: MYFILE: myheader!" in c.out

        # It also works in local flow
        c.run("source .")
        assert "conanfile.py (pkg/0.1): MYCMAKE: mycmake" in c.out
        assert "conanfile.py (pkg/0.1): MYFILE: myheader!" in c.out
        assert c.load("source/src/myfile.h") == "myheader!"
        assert c.load("source/CMakeLists.txt") == "mycmake"

    def test_clone_url_not_hidden(self):
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
                    git.fetch_commit(url="{url}", commit="{commit}", hide_url=False)
            """)
        folder = os.path.join(temp_folder(), "myrepo")
        url, commit = create_local_git_repo(files={"CMakeLists.txt": "mycmake"}, folder=folder)

        c = TestClient(light=True)
        c.save({"conanfile.py": conanfile.format(url=url, commit=commit)})
        c.run("create . -v")
        # Clone URL is explicitly printed
        assert f'pkg/0.1: RUN: git remote add origin "{url}"' in c.out

        # It also works in local flow
        c.run("source .")
        assert f'conanfile.py (pkg/0.1): RUN: git remote add origin "{url}"' in c.out


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


@pytest.mark.tool("git")
class TestGitBasicSCMFlow:
    """ Build the full new SCM approach:
    - export() captures the URL and commit with get_url_and_commit(
    - export() stores it in conandata.yml
    - source() recovers the info from conandata.yml and clones it
    """
    conanfile_full = textwrap.dedent("""
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
    conanfile_scm = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.scm import Git
        from conan.tools.files import load, trim_conandata

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def export(self):
                Git(self).coordinates_to_conandata()
                trim_conandata(self)  # to test it does not affect

            def layout(self):
                self.folders.source = "."

            def source(self):
                Git(self).checkout_from_conandata_coordinates()
                self.output.info("MYCMAKE: {}".format(load(self, "CMakeLists.txt")))
                self.output.info("MYFILE: {}".format(load(self, "src/myfile.h")))

            def build(self):
                cmake = os.path.join(self.source_folder, "CMakeLists.txt")
                file_h = os.path.join(self.source_folder, "src/myfile.h")
                self.output.info("MYCMAKE-BUILD: {}".format(load(self, cmake)))
                self.output.info("MYFILE-BUILD: {}".format(load(self, file_h)))
        """)

    @pytest.mark.parametrize("conanfile_scm", [False, True])
    def test_full_scm(self, conanfile_scm):
        conanfile = self.conanfile_scm if conanfile_scm else self.conanfile_full
        folder = os.path.join(temp_folder(), "myrepo")
        url, commit = create_local_git_repo(files={"conanfile.py": conanfile,
                                                   "src/myfile.h": "myheader!",
                                                   "CMakeLists.txt": "mycmake"}, folder=folder)

        c = TestClient(default_server_user=True)
        c.run_command('git clone "file://{}" .'.format(url))
        c.run("create .")
        assert "pkg/0.1: MYCMAKE: mycmake" in c.out
        assert "pkg/0.1: MYFILE: myheader!" in c.out
        c.run("upload * -c -r=default")

        # Do a change and commit, this commit will not be used by package
        save_files(path=folder, files={"src/myfile.h": "my2header2!"})
        git_add_changes_commit(folder=folder)

        # use another fresh client
        c2 = TestClient(servers=c.servers)
        c2.run("install --requires=pkg/0.1@ --build=pkg*")
        assert "pkg/0.1: MYCMAKE: mycmake" in c2.out
        assert "pkg/0.1: MYFILE: myheader!" in c2.out

        # local flow
        c.run("install .")
        c.run("build .")
        assert "conanfile.py (pkg/0.1): MYCMAKE-BUILD: mycmake" in c.out
        assert "conanfile.py (pkg/0.1): MYFILE-BUILD: myheader!" in c.out

    @pytest.mark.parametrize("conanfile_scm", [False, True])
    def test_branch_flow(self, conanfile_scm):
        """ Testing that when a user creates a branch, and pushes a commit,
        the package can still be built from sources, and get_url_and_commit() captures the
        remote URL and not the local
        """
        conanfile = self.conanfile_scm if conanfile_scm else self.conanfile_full
        url = git_create_bare_repo()
        c = TestClient(default_server_user=True)
        c.run_command('git clone "file://{}" .'.format(url))
        c.save({"conanfile.py": conanfile,
                "src/myfile.h": "myheader!",
                "CMakeLists.txt": "mycmake"})
        c.run_command("git checkout -b mybranch")
        git_add_changes_commit(folder=c.current_folder)
        c.run_command("git push --set-upstream origin mybranch")
        c.run("create .")
        assert "pkg/0.1: MYCMAKE: mycmake" in c.out
        assert "pkg/0.1: MYFILE: myheader!" in c.out
        c.run("upload * -c -r=default")
        rmdir(c.current_folder)  # Remove current folder to make sure things are not used from here

        # use another fresh client
        c2 = TestClient(servers=c.servers)
        c2.run("install --requires=pkg/0.1@ --build=pkg*")
        assert "pkg/0.1: MYCMAKE: mycmake" in c2.out
        assert "pkg/0.1: MYFILE: myheader!" in c2.out


@pytest.mark.tool("git")
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
        c.run("upload * -c -r=default")

        # Do a change and commit, this commit will not be used by package
        save_files(path=folder, files={"src/myfile.h": "my2header2!"})
        git_add_changes_commit(folder=folder)

        # use another fresh client
        c2 = TestClient(servers=c.servers)
        c2.run("install --requires=pkg/0.1@ --build=pkg*")
        assert "pkg/0.1: MYCMAKE: mycmake" in c2.out
        assert "pkg/0.1: MYFILE: myheader!" in c2.out

        # local flow
        c.run("install conan")
        c.run("build conan")
        assert "conanfile.py (pkg/0.1): MYCMAKE-BUILD: mycmake" in c.out
        assert "conanfile.py (pkg/0.1): MYFILE-BUILD: myheader!" in c.out


@pytest.mark.tool("git")
class TestGitMonorepoSCMFlow:
    """ Build the full new SCM approach:
    Same as above but with a monorepo with multiple subprojects
    """
    # TODO: swap_child_folder() not documented, not public usage
    conanfile = textwrap.dedent("""
        import os, shutil
        from conan import ConanFile
        from conan.tools.scm import Git
        from conan.tools.files import load, update_conandata, move_folder_contents

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
                move_folder_contents(self, os.path.join(self.source_folder, sources["folder"]),
                                    self.source_folder)

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
        c.run("upload * -c -r=default")

        # use another fresh client
        c2 = TestClient(servers=c.servers)
        c2.run("install --requires=pkg2/0.1@ --build=*")
        assert "pkg1/0.1: Checkout: {}".format(commit) in c2.out
        assert "pkg1/0.1: MYCMAKE-BUILD: mycmake1!" in c2.out
        assert "pkg1/0.1: MYFILE-BUILD: myheader1!" in c2.out
        assert "pkg2/0.1: MYCMAKE-BUILD: mycmake2!" in c2.out
        assert "pkg2/0.1: MYFILE-BUILD: my2header!" in c2.out

    @pytest.mark.tool("cmake")
    def test_exports_sources_common_code_layout(self):
        """ This is a copy of test_exports_sources_common_code_layout in test_in_subfolder.py
        but instead of using "exports", trying to implement it with Git features
        """
        c = TestClient()
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.cmake import cmake_layout, CMake
            from conan.tools.files import load, copy, save, update_conandata, move_folder_contents
            from conan.tools.scm import Git

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "CMakeToolchain"

                def export(self):
                    git = Git(self)
                    scm_url, scm_commit = git.get_url_and_commit()
                    update_conandata(self, {"sources": {"commit": scm_commit, "url": scm_url}})

                def layout(self):
                    self.folders.root = ".."
                    self.folders.subproject = "pkg"
                    cmake_layout(self)

                def source(self):
                    git = Git(self)
                    sources = self.conan_data["sources"]
                    git.clone(url=sources["url"], target=".")
                    git.checkout(commit=sources["commit"])
                    # Layout is pkg/pkg/<files> and pkg/common/<files>
                    # Final we want is pkg/<files> and common/<files>
                    # NOTE: This abs_path is IMPORTANT to avoid the trailing "."
                    src_folder = os.path.abspath(self.source_folder)
                    move_folder_contents(self, src_folder, os.path.dirname(src_folder))

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
                    self.run(os.path.join(self.cpp.build.bindirs[0], "myapp"))
                """)
        cmake_include = "include(${CMAKE_CURRENT_LIST_DIR}/../common/myutils.cmake)"
        c.save({"pkg/conanfile.py": conanfile,
                "pkg/app.cpp": gen_function_cpp(name="main", includes=["../common/myheader"],
                                                preprocessor=["MYDEFINE"]),
                "pkg/CMakeLists.txt": gen_cmakelists(appsources=["app.cpp"],
                                                     custom_content=cmake_include),
                "common/myutils.cmake": 'message(STATUS "MYUTILS.CMAKE!")',
                "common/myheader.h": '#define MYDEFINE "MYDEFINEVALUE"'})
        c.init_git_repo()

        c.run("create pkg")
        assert "MYUTILS.CMAKE!" in c.out
        assert "main: Release!" in c.out
        assert "MYDEFINE: MYDEFINEVALUE" in c.out

        # Local flow
        c.run("install pkg")
        c.run("build pkg")
        assert "MYUTILS.CMAKE!" in c.out
        assert "main: Release!" in c.out
        assert "MYDEFINE: MYDEFINEVALUE" in c.out

        c.run("install pkg -s build_type=Debug")
        c.run("build pkg -s build_type=Debug")
        assert "MYUTILS.CMAKE!" in c.out
        assert "main: Debug!" in c.out
        assert "MYDEFINE: MYDEFINEVALUE" in c.out


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

    def test_git_run(self):
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.scm import Git

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                def export(self):
                    git = Git(self)
                    self.output.info(git.run("--version"))
            """)

        c = TestClient()
        c.save({"conan/conanfile.py": conanfile})
        c.init_git_repo()
        c.run("export conan")
        assert "pkg/0.1: git version" in c.out


class TestGitIncluded:
    def test_git_included(self):
        conanfile = textwrap.dedent("""
            import os
            import shutil
            from conan import ConanFile
            from conan.tools.scm import Git

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"

                def export_sources(self):
                    git = Git(self)
                    included = git.included_files()
                    for i in included:
                        dst =  os.path.join(self.export_sources_folder, i)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(i, dst)

                def source(self):
                    self.output.info("SOURCES: {}!!".format(sorted(os.listdir("."))))
                    self.output.info("SOURCES_SUB: {}!!".format(sorted(os.listdir("sub"))))
            """)

        c = TestClient()
        c.save({"conanfile.py": conanfile,
                ".gitignore": "*.txt",
                "myfile.txt": "test",
                "myfile.other": "othertest",
                "sub/otherfile": "other"})
        c.init_git_repo()
        c.run("create .")
        assert "pkg/0.1: SOURCES: ['.gitignore', 'conanfile.py', 'myfile.other', 'sub']!!" in c.out
        assert "pkg/0.1: SOURCES_SUB: ['otherfile']!!" in c.out

    def test_git_included_subfolder(self):
        conanfile = textwrap.dedent("""
            import os
            import shutil
            from conan import ConanFile
            from conan.tools.scm import Git

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"

                def export_sources(self):
                    git = Git(self, "src")
                    included = git.included_files()
                    for i in included:
                        shutil.copy2(i, self.export_sources_folder)

                def source(self):
                    self.output.info("SOURCES: {}!!".format(sorted(os.listdir("."))))
            """)

        c = TestClient()
        c.save({"conanfile.py": conanfile,
                ".gitignore": "*.txt",
                "somefile": "some",
                "src/myfile.txt": "test",
                "src/myfile.other": "othertest"})
        c.init_git_repo()
        c.run("create .")
        assert "pkg/0.1: SOURCES: ['myfile.other']!!" in c.out


def test_capture_git_tag():
    """
    A local repo, without remote, will have commit, but no URL
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.scm import Git

        class Pkg(ConanFile):
            name = "pkg"

            def set_version(self):
                git = Git(self, self.recipe_folder)
                self.version = git.run("describe --tags")
        """)
    c.save({"conanfile.py": conanfile})
    c.init_git_repo()
    c.run_command("git tag 1.2")
    c.run("install .")
    assert "pkg/1.2" in c.out
    c.run("create .")
    assert "pkg/1.2" in c.out
    c.run("install --requires=pkg/1.2")
    assert "pkg/1.2" in c.out


@pytest.mark.tool("git")
class TestGitShallowTagClone:
    """
    When we do a shallow clone of a repo with a specific tag/branch, it doesn't
    clone any of the git history.  When we check to see if a commit is in the
    repo, we fallback to a git fetch if we can't verify the commit locally.
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

    def test_find_tag_in_remote(self):
        """
        a shallow cloned repo won't have the new commit locally, but can fetch it.
        """
        folder = temp_folder()
        url, commit = create_local_git_repo(files={"conanfile.py": self.conanfile}, folder=folder)

        c = TestClient()
        # Create a tag
        with c.chdir(folder):
            c.run_command('git tag 1.0.0')

        # Do a shallow clone of our tag
        c.run_command('git clone --depth=1 --branch 1.0.0 "{}" myclone'.format(folder))
        with c.chdir("myclone"):
            c.run("export .")
            assert "pkg/0.1: COMMIT: {}".format(commit) in c.out
            assert "pkg/0.1: URL: {}".format(url) in c.out
            assert "pkg/0.1: COMMIT IN REMOTE: True" in c.out
            assert "pkg/0.1: DIRTY: False" in c.out

    def test_detect_commit_not_in_remote(self):
        """
        a shallow cloned repo won't have new commit in remote
        """
        folder = temp_folder()
        url, commit = create_local_git_repo(files={"conanfile.py": self.conanfile}, folder=folder)

        c = TestClient()
        # Create a tag
        with c.chdir(folder):
            c.run_command('git tag 1.0.0')

        # Do a shallow clone of our tag
        c.run_command('git clone --depth=1 --branch 1.0.0 "{}" myclone'.format(folder))
        with c.chdir("myclone"):
            c.save({"conanfile.py": self.conanfile + "\n# some coment!"})
            new_commit = git_add_changes_commit(c.current_folder)

            c.run("export .")
            assert "pkg/0.1: COMMIT: {}".format(new_commit) in c.out
            assert "pkg/0.1: URL: {}".format(url) in c.out
            assert "pkg/0.1: COMMIT IN REMOTE: False" in c.out
            assert "pkg/0.1: DIRTY: False" in c.out
