import os

# Check it is importable from tools
from conan.tools.files import rm
from conans.client.tools.files import chdir
from conans.test.utils.test_files import temp_folder
from conans.util.files import save_files


def test_remove_files_by_mask_recursively():
    tmpdir = temp_folder()

    with chdir(tmpdir):
        os.makedirs("subdir")
        os.makedirs("dir.pdb")
        os.makedirs(os.path.join("subdir", "deepdir"))

    save_files(tmpdir, {"1.txt": "",
                        "1.pdb": "",
                        "1.pdb1": "",
                        os.path.join("subdir", "2.txt"): "",
                        os.path.join("subdir", "2.pdb"): "",
                        os.path.join("subdir", "2.pdb1"): "",
                        os.path.join("subdir", "deepdir", "3.txt"): "",
                        os.path.join("subdir", "deepdir", "3.pdb"): "",
                        os.path.join("subdir", "deepdir", "3.pdb1"): ""})

    rm(None, "*.sh", tmpdir, recursive=True)

    removed_files = rm(None, "*.pdb", tmpdir, recursive=True)

    assert os.path.isdir(os.path.join(tmpdir, "dir.pdb"))

    assert os.path.isfile(os.path.join(tmpdir, "1.txt"))
    assert not os.path.isfile(os.path.join(tmpdir, "1.pdb"))
    assert os.path.isfile(os.path.join(tmpdir, "1.pdb1"))

    assert os.path.isfile(os.path.join(tmpdir, "subdir", "2.txt"))
    assert not os.path.isfile(os.path.join(tmpdir, "subdir", "2.pdb"))
    assert os.path.isfile(os.path.join(tmpdir, "subdir", "2.pdb1"))

    assert os.path.isfile(os.path.join(tmpdir, "subdir", "deepdir", "3.txt"))
    assert not os.path.isfile(os.path.join(tmpdir, "subdir", "deepdir", "3.pdb"))
    assert os.path.isfile(os.path.join(tmpdir, "subdir", "deepdir", "3.pdb1"))

    rm(None, "*.pdb", tmpdir, recursive=True)


def test_remove_files_by_mask_non_recursively():
    tmpdir = temp_folder()
    with chdir(tmpdir):
        os.makedirs("subdir")

    save_files(tmpdir, {"1.txt": "",
                        "1.pdb": "",
                        "1.pdb1": "",
                        os.path.join("subdir", "2.txt"): "",
                        os.path.join("subdir", "2.pdb"): "",
                        os.path.join("subdir", "2.pdb1"): ""})

    rm(None, "*.pdb", tmpdir)
    assert not os.path.exists(os.path.join(tmpdir, "1.pdb"))
    assert os.path.exists(os.path.join(tmpdir, "subdir", "2.pdb"))

    assert os.path.exists(os.path.join(tmpdir, "1.txt"))
    assert os.path.exists(os.path.join(tmpdir, "subdir", "2.txt"))
