import os
import unittest

from conans.client.tools.files import remove_files_by_mask, chdir
from conans.test.utils.tools import TestClient


class RemoveFilesByMaskTest(unittest.TestCase):
    def remove_files_by_mask_test(self):
        client = TestClient()
        tmpdir = client.current_folder

        with chdir(tmpdir):
            os.makedirs("subdir")
            os.makedirs("dir.pdb")
            os.makedirs(os.path.join("subdir", "deepdir"))

        client.save({"1.txt": "",
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
