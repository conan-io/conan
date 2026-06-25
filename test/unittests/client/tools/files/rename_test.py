import os

from conan.tools.files import rename
from conan.test.utils.tools import TestClient
from conan.internal.util.files import chdir


class TestRename:

    def test_rename(self):
        client = TestClient()
        folder = client.current_folder

        sub_space_dir = "sub dir"
        with chdir(folder):
            os.makedirs(sub_space_dir)
            os.makedirs(os.path.join(sub_space_dir, "dir.pdb"))
            os.makedirs(os.path.join(sub_space_dir, "middir"))
            os.makedirs(os.path.join(sub_space_dir, "middir", "deepdir"))

        client.save({os.path.join(sub_space_dir, "1.txt"): "",
                     os.path.join(sub_space_dir, "1.pdb"): "",
                     os.path.join(sub_space_dir, "1.pdb1"): "",
                     os.path.join(sub_space_dir, "dir.pdb", "2.txt"): "",
                     os.path.join(sub_space_dir, "dir.pdb", "2.pdb"): "",
                     os.path.join(sub_space_dir, "dir.pdb", "2.pdb1"): "",
                     os.path.join(sub_space_dir, "middir", "3.txt"): "",
                     os.path.join(sub_space_dir, "middir", "3.pdb"): "",
                     os.path.join(sub_space_dir, "middir", "3.pdb1"): "",
                     os.path.join(sub_space_dir, "middir", "deepdir", "4.txt"): "",
                     os.path.join(sub_space_dir, "middir", "deepdir", "4.pdb"): "",
                     os.path.join(sub_space_dir, "middir", "deepdir", "4.pdb1"): ""
                     })

        def verify_dir(basedir):
            assert os.path.isdir(basedir)

            assert os.path.isfile(os.path.join(basedir, "1.txt"))
            assert os.path.isfile(os.path.join(basedir, "1.pdb"))
            assert os.path.isfile(os.path.join(basedir, "1.pdb1"))

            assert os.path.isdir(os.path.join(basedir, "dir.pdb"))
            assert os.path.isfile(os.path.join(basedir, "dir.pdb", "2.txt"))
            assert os.path.isfile(os.path.join(basedir, "dir.pdb", "2.pdb"))
            assert os.path.isfile(os.path.join(basedir, "dir.pdb", "2.pdb1"))

            assert os.path.isdir(os.path.join(basedir, "middir"))
            assert os.path.isfile(os.path.join(basedir, "middir", "3.txt"))
            assert os.path.isfile(os.path.join(basedir, "middir", "3.pdb"))
            assert os.path.isfile(os.path.join(basedir, "middir", "3.pdb1"))

            assert os.path.isdir(os.path.join(basedir, "middir", "deepdir"))
            assert os.path.isfile(os.path.join(basedir, "middir", "deepdir", "4.txt"))
            assert os.path.isfile(os.path.join(basedir, "middir", "deepdir", "4.pdb"))
            assert os.path.isfile(os.path.join(basedir, "middir", "deepdir", "4.pdb1"))

        verify_dir(os.path.join(folder, sub_space_dir))

        with chdir(folder):
            rename(None, sub_space_dir, "dst dir")
            verify_dir(os.path.join(folder, "dst dir"))

            rename(None, "dst dir", "subdir")
            verify_dir(os.path.join(folder, "subdir"))

            rename(None, os.path.join("subdir", "1.txt"), "t.txt")
            assert os.path.isfile(os.path.join(folder, "t.txt"))
            assert not os.path.isfile(os.path.join(folder, "subdir", "1.txt"))

    def test_rename_empty_folder(self):
        client = TestClient()
        old_folder = os.path.join(client.current_folder, "old_folder")
        os.mkdir(old_folder)
        new_folder = os.path.join(client.current_folder, "new_folder")
        rename(None, old_folder, new_folder)
        assert not os.path.exists(old_folder)
        assert os.path.exists(new_folder)
