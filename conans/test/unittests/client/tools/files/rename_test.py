import os
import unittest

from conans.client.tools.files import rename, chdir
from conans.test.utils.tools import TestClient


class RenameTest(unittest.TestCase):
    def verify_dir(self, basedir):
        self.assertTrue(os.path.isdir(basedir))

        self.assertTrue(os.path.isfile(os.path.join(basedir, "1.txt")))
        self.assertTrue(os.path.isfile(os.path.join(basedir, "1.pdb")))
        self.assertTrue(os.path.isfile(os.path.join(basedir, "1.pdb1")))

        self.assertTrue(os.path.isdir(os.path.join(basedir, "dir.pdb")))
        self.assertTrue(os.path.isfile(os.path.join(basedir, "dir.pdb", "2.txt")))
        self.assertTrue(os.path.isfile(os.path.join(basedir, "dir.pdb", "2.pdb")))
        self.assertTrue(os.path.isfile(os.path.join(basedir, "dir.pdb", "2.pdb1")))

        self.assertTrue(os.path.isdir(os.path.join(basedir, "middir")))
        self.assertTrue(os.path.isfile(os.path.join(basedir, "middir", "3.txt")))
        self.assertTrue(os.path.isfile(os.path.join(basedir, "middir", "3.pdb")))
        self.assertTrue(os.path.isfile(os.path.join(basedir, "middir", "3.pdb1")))

        self.assertTrue(os.path.isdir(os.path.join(basedir, "middir", "deepdir")))
        self.assertTrue(os.path.isfile(os.path.join(basedir, "middir", "deepdir", "4.txt")))
        self.assertTrue(os.path.isfile(os.path.join(basedir, "middir", "deepdir", "4.pdb")))
        self.assertTrue(os.path.isfile(os.path.join(basedir, "middir", "deepdir", "4.pdb1")))

    def test_rename(self):
        client = TestClient()
        tmpdir = client.current_folder

        sub_space_dir = "sub dir"
        with chdir(tmpdir):
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
        self.verify_dir(os.path.join(tmpdir, sub_space_dir))

        with chdir(tmpdir):
            rename(sub_space_dir, "dst dir")
            self.verify_dir(os.path.join(tmpdir, "dst dir"))

            rename("dst dir", "subdir")
            self.verify_dir(os.path.join(tmpdir, "subdir"))

            rename(os.path.join("subdir", "1.txt"), "t.txt")
            self.assertTrue(os.path.isfile(os.path.join(tmpdir, "t.txt")))
            self.assertFalse(os.path.isfile(os.path.join(tmpdir, "subdir", "1.txt")))

    def test_rename_empty_folder(self):
        client = TestClient()
        old_folder = os.path.join(client.current_folder, "old_folder")
        os.mkdir(old_folder)
        new_folder = os.path.join(client.current_folder, "new_folder")
        rename(old_folder, new_folder)
        self.assertFalse(os.path.exists(old_folder))
        self.assertTrue(os.path.exists(new_folder))
