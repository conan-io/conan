import os
import shutil
import time
import unittest

from conans.client.cmd.uploader import compress_files
from conans.client.tools.files import chdir
from conans.paths import PACKAGE_TGZ_NAME
from conans.test.utils.test_files import temp_folder
from conans.util.files import md5sum, mkdir, path_exists, save, save_files


def hardlinks_supported():
    if not hasattr(os, "link"):
        return False
    tmpdir = temp_folder()
    try:
        save_files(tmpdir, {"a": ""})
        with chdir(tmpdir):
            os.link("a", "b")
            return os.stat("a").st_ino == os.stat("b").st_ino
    except OSError:
        return False
    finally:
        shutil.rmtree(tmpdir)

class FilesTest(unittest.TestCase):

    def test_md5_compress(self):
        """
        The md5 of a tgz should be the same if the files inside are the same
        """
        folder = temp_folder()
        save(os.path.join(folder, "one_file.txt"), b"The contents")
        save(os.path.join(folder, "Two_file.txt"), b"Two contents")

        files = {
            "one_file.txt": os.path.join(folder, "one_file.txt"),
            "Two_file.txt": os.path.join(folder, "Two_file.txt"),
        }

        compress_files(files, {}, PACKAGE_TGZ_NAME, dest_dir=folder)
        file_path = os.path.join(folder, PACKAGE_TGZ_NAME)

        md5_a = md5sum(file_path)
        self.assertEqual(md5_a, "df220cfbc0652e8992a89a77666c03b5")

        time.sleep(1)  # Timestamps change

        folder = temp_folder()
        compress_files(files, {}, PACKAGE_TGZ_NAME, dest_dir=folder)
        file_path = os.path.join(folder, PACKAGE_TGZ_NAME)

        md5_b = md5sum(file_path)

        self.assertEqual(md5_a, md5_b)

    def test_path_exists(self):
        """
        Unit test of path_exists
        """
        tmp_dir = temp_folder()
        tmp_dir = os.path.join(tmp_dir, "WhatEver")
        new_path = os.path.join(tmp_dir, "CapsDir")
        mkdir(new_path)
        self.assertTrue(path_exists(new_path, tmp_dir))
        self.assertFalse(path_exists(os.path.join(tmp_dir, "capsdir"), tmp_dir))

    @unittest.skipUnless(hardlinks_supported(), "requires hard-links")
    def test_hard_links(self):
        """
        test hard links are preserved during the packaging
        """
        tmpdir = temp_folder()
        a = os.path.join(tmpdir, "one_file.txt")
        b = os.path.join(tmpdir, "two_file.txt")
        save(a, b"The contents")
        os.link(a, b)

        files = {"one_file.txt": a, "two_file.txt": b}
        compress_files(files, {}, PACKAGE_TGZ_NAME, dest_dir=tmpdir)

        import tarfile

        dst = temp_folder()
        with tarfile.open(os.path.join(tmpdir, PACKAGE_TGZ_NAME)) as t:
            t.extractall(dst)

        a = os.path.join(dst, "one_file.txt")
        b = os.path.join(dst, "two_file.txt")

        md5_a = md5sum(a)
        md5_b = md5sum(b)

        self.assertEqual(md5_a, md5_b)

        self.assertEqual(os.stat(a).st_ino, os.stat(b).st_ino)
