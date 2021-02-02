import os
import unittest

# Check it is importable from tools
from conans.tools import remove_files_by_mask
from conans.client.tools.files import chdir
from conans.test.utils.test_files import temp_folder
from conans.util.files import save_files


class RemoveFilesByMaskTest(unittest.TestCase):
    def test_remove_files_by_mask(self):
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

        removed_files = remove_files_by_mask(tmpdir, "*.sh")
        self.assertEqual(removed_files, [])

        removed_files = remove_files_by_mask(tmpdir, "*.pdb")

        self.assertTrue(os.path.isdir(os.path.join(tmpdir, "dir.pdb")))

        self.assertTrue(os.path.isfile(os.path.join(tmpdir, "1.txt")))
        self.assertFalse(os.path.isfile(os.path.join(tmpdir, "1.pdb")))
        self.assertTrue(os.path.isfile(os.path.join(tmpdir, "1.pdb1")))

        self.assertTrue(os.path.isfile(os.path.join(tmpdir, "subdir", "2.txt")))
        self.assertFalse(os.path.isfile(os.path.join(tmpdir, "subdir", "2.pdb")))
        self.assertTrue(os.path.isfile(os.path.join(tmpdir, "subdir", "2.pdb1")))

        self.assertTrue(os.path.isfile(os.path.join(tmpdir, "subdir", "deepdir", "3.txt")))
        self.assertFalse(os.path.isfile(os.path.join(tmpdir, "subdir", "deepdir", "3.pdb")))
        self.assertTrue(os.path.isfile(os.path.join(tmpdir, "subdir", "deepdir", "3.pdb1")))

        self.assertEqual(set(removed_files), {"1.pdb",
                                              os.path.join("subdir", "2.pdb"),
                                              os.path.join("subdir", "deepdir", "3.pdb")})

        removed_files = remove_files_by_mask(tmpdir, "*.pdb")
        self.assertEqual(removed_files, [])
