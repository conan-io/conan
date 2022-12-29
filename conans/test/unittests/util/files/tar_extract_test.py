# coding=utf-8

import os
import platform
import tarfile
import unittest

import pytest

from conans.client.tools.files import chdir
from conans.model.manifest import gather_files
from conans.test.utils.test_files import temp_folder
from conans.util.files import tar_extract, gzopen_without_timestamps, save


class TarExtractTest(unittest.TestCase):

    def setUp(self):
        self.tmp_folder = temp_folder()
        with chdir(self.tmp_folder):
            # Create a couple of files
            ori_files_dir = os.path.join(self.tmp_folder, "ori")
            file1 = os.path.join(ori_files_dir, "file1")
            file2 = os.path.join(ori_files_dir, "folder", "file2")
            save(file1, "")
            save(file2, "")

            # Create a tar.gz file with the above files
            self.tgz_file = os.path.join(self.tmp_folder, "file.tar.gz")
            with open(self.tgz_file, "wb") as tgz_handle:
                tgz = gzopen_without_timestamps("name", mode="w", fileobj=tgz_handle)

                files, _ = gather_files(ori_files_dir)
                for filename, abs_path in files.items():
                    info = tarfile.TarInfo(name=filename)
                    with open(file1, 'rb') as file_handler:
                        tgz.addfile(tarinfo=info, fileobj=file_handler)
                tgz.close()

    @pytest.mark.skipif(platform.system() != "Linux", reason="Requires Linux")
    def test_link_folder(self):
        # If there is a linked folder in the current directory that matches one file in the tar.
        # https://github.com/conan-io/conan/issues/4959

        # Once unpackaged, this is the content of the destination directory
        def check_files(destination_dir):
            d = sorted(os.listdir(destination_dir))
            self.assertListEqual(d, ["file1", "folder"])
            d_folder = os.listdir(os.path.join(destination_dir, "folder"))
            self.assertEqual(d_folder, ["file2"])

        working_dir = temp_folder()
        with chdir(working_dir):
            # Unpack and check
            destination_dir = os.path.join(self.tmp_folder, "dest")
            with open(self.tgz_file, 'rb') as file_handler:
                tar_extract(file_handler, destination_dir)
            check_files(destination_dir)

            # Unpack and check (now we have a symlinked local folder)
            os.symlink(temp_folder(), "folder")
            destination_dir = os.path.join(self.tmp_folder, "dest2")
            with open(self.tgz_file, 'rb') as file_handler:
                tar_extract(file_handler, destination_dir)
            check_files(destination_dir)
