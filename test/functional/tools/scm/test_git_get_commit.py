import os

import pytest

from conan.tools.scm import Git
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.tools import TestClient
from conans.util.files import chdir
from conans.util.runners import conan_run


@pytest.mark.tool("git")
def test_change_branch_in_root_commit():
    """
    https://github.com/conan-io/conan/issues/10971#issuecomment-1089316912
    """
    c = TestClient()
    c.save({"root.txt": "", "subfolder/subfolder.txt": ""})
    c.run_command("git init .")
    c.run_command("git checkout -B master")
    c.run_command('git config user.name myname')
    c.run_command('git config user.email myname@mycompany.com')
    c.run_command("git add .")
    c.run_command('git commit -m "initial commit"')
    c.run_command("git checkout -b change_branch")
    c.save({"subfolder/subfolder.txt": "CHANGED"})
    c.run_command("git add .")
    c.run_command('git commit -m "second commit"')
    c.run_command("git checkout master")
    c.run_command('git merge --no-ff change_branch -m "Merge branch"')

    conanfile = ConanFileMock({}, runner=conan_run)
    git = Git(conanfile, folder=c.current_folder)
    commit_conan = git.get_commit()

    c.run_command("git rev-parse HEAD")
    commit_real = str(c.out).splitlines()[0]
    assert commit_conan == commit_real


@pytest.mark.tool("git")
def test_multi_folder_repo():
    c = TestClient()
    c.save({"lib_a/conanfile.py": ""})
    c.run_command("git init .")
    c.run_command('git config user.name myname')
    c.run_command('git config user.email myname@mycompany.com')
    c.run_command("git add .")
    c.run_command('git commit -m "lib_a commit"')
    c.save({"lib_b/conanfile.py": ""})
    c.run_command("git add .")
    c.run_command('git commit -m "lib_b commit"')
    c.save({"lib_c/conanfile.py": ""})
    c.run_command("git add .")
    c.run_command('git commit -m "lib_c commit"')
    c.save({"root_change": ""})
    c.run_command("git add .")
    c.run_command('git commit -m "root change"')

    # Git object for lib_a
    conanfile = ConanFileMock({}, runner=conan_run)
    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_a"))
    commit_libA = git.get_commit()

    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_b"))
    commit_libB = git.get_commit()

    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_c"))
    commit_libC = git.get_commit()

    git = Git(conanfile, folder=c.current_folder)
    commit_root = git.get_commit()

    # All different
    assert len({commit_libA, commit_libB, commit_libC, commit_root}) == 4

    c.run_command("git rev-parse HEAD")
    commit_real = str(c.out).splitlines()[0]
    assert commit_root == commit_real

    # New commit in A
    c.save({"lib_a/conanfile.py": "CHANGED"})
    c.run_command("git add .")
    c.run_command('git commit -m "lib_a commit2"')

    # Git object for lib_a
    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_a"))
    new_commit_libA = git.get_commit()

    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_b"))
    new_commit_libB = git.get_commit()

    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_c"))
    new_commit_libC = git.get_commit()

    git = Git(conanfile, folder=c.current_folder)
    new_commit_root = git.get_commit()

    assert new_commit_libA != commit_libA
    assert new_commit_libB == commit_libB
    assert new_commit_libC == commit_libC
    assert new_commit_root != commit_root

    c.run_command("git rev-parse HEAD")
    commit_real = str(c.out).splitlines()[0]
    assert new_commit_root == commit_real


@pytest.mark.tool("git")
def test_relative_folder_repo():
    c = TestClient()
    c.save({"lib_a/conanfile.py": ""})
    c.run_command("git init .")
    c.run_command('git config user.name myname')
    c.run_command('git config user.email myname@mycompany.com')
    c.run_command("git add .")
    c.run_command('git commit -m "lib_a commit"')
    c.save({"lib_b/conanfile.py": ""})
    c.run_command("git add .")
    c.run_command('git commit -m "lib_b commit"')
    c.save({"lib_c/conanfile.py": ""})
    c.run_command("git add .")
    c.run_command('git commit -m "lib_c commit"')
    c.save({"root_change": ""})
    c.run_command("git add .")
    c.run_command('git commit -m "root change"')

    conanfile = ConanFileMock({}, runner=conan_run)
    # Relative paths for folders, from the current_folder
    with chdir(c.current_folder):
        git = Git(conanfile, folder="lib_a")
        commit_libA = git.get_commit()

        git = Git(conanfile, folder="lib_b")
        commit_libB = git.get_commit()

        git = Git(conanfile, folder="./lib_c")
        commit_libC = git.get_commit()

        # this is folder default, but be explicit
        git = Git(conanfile, folder=".")
        commit_root = git.get_commit()

    # All different
    assert len({commit_libA, commit_libB, commit_libC, commit_root}) == 4

    # Compare to Full paths
    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_a"))
    full_commit_libA = git.get_commit()

    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_b"))
    full_commit_libB = git.get_commit()

    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_c"))
    full_commit_libC = git.get_commit()

    git = Git(conanfile, folder=c.current_folder)
    full_commit_root = git.get_commit()

    assert full_commit_libA == commit_libA
    assert full_commit_libB == commit_libB
    assert full_commit_libC == commit_libC
    assert full_commit_root == commit_root

    # Sanity checks
    c.run_command("git rev-parse HEAD")
    commit_real_root = str(c.out).splitlines()[0]
    assert commit_real_root == commit_root

    c.run_command("git rev-list -n 1 --full-history HEAD -- lib_a")
    commit_real_libA = str(c.out).splitlines()[0]
    assert commit_real_libA == commit_libA


@pytest.mark.tool("git")
def test_submodule_repo():
    c = TestClient()
    c.save({"conanfile.py": ""})
    c.run_command("git init .")
    c.run_command('git config user.name myname')
    c.run_command('git config user.email myname@mycompany.com')
    c.run_command("git add .")
    c.run_command('git commit -m "Initial commit"')
    c.run_command('git clone . source_subfolder')
    c.run_command('git submodule add ../ source_subfolder')
    c.run_command('git commit -m "submodule commit"')
    c.save({"root_change": ""})
    c.run_command("git add .")
    c.run_command('git commit -m "root change"')

    conanfile = ConanFileMock({}, runner=conan_run)
    with chdir(c.current_folder):
        # default case
        git = Git(conanfile)
        commit_root = git.get_commit()

        # Relative paths
        git = Git(conanfile, folder="source_subfolder")
        commit_relA = git.get_commit()

        git = Git(conanfile, folder="./source_subfolder")
        commit_relB = git.get_commit()

        # Full path
        git = Git(conanfile, folder=os.path.join(c.current_folder, "source_subfolder"))
        commit_full = git.get_commit()

    assert commit_relA == commit_relB
    assert commit_relA == commit_full
    assert commit_root != commit_full

    # This is the commit which modified the tree in the containing repo
    # not the commit which the submodule is at
    c.run_command("git rev-list HEAD -n 1 --full-history -- source_subfolder")
    commit_submodule = str(c.out).splitlines()[0]
    assert commit_submodule != commit_full
