import os
import tarfile
import unittest

import six

from conans.client.tools import untargz, unzip
from conans.client.tools.files import chdir, save
from conans.test.utils.test_files import temp_folder
from conans.errors import ConanException
from conans.model.manifest import gather_files
from conans.test.functional.command.config_install_test import zipdir
from conans.util.files import gzopen_without_timestamps


class ZipExtractPlainTest(unittest.TestCase):

    def test_plain_zip(self):
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            ori_files_dir = os.path.join(tmp_folder, "subfolder-1.2.3")
            file1 = os.path.join(ori_files_dir, "file1")
            file2 = os.path.join(ori_files_dir, "folder", "file2")
            file3 = os.path.join(ori_files_dir, "file3")

            save(file1, "")
            save(file2, "")
            save(file3, "")

        zip_file = os.path.join(tmp_folder, "myzip.zip")
        zipdir(tmp_folder, zip_file)

        # Tgz unzipped regularly
        extract_folder = temp_folder()
        unzip(zip_file, destination=extract_folder, strip_root=False)
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "file1")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "folder",
                                                    "file2")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "file3")))

        # Extract without the subfolder
        extract_folder = temp_folder()
        unzip(zip_file, destination=extract_folder, strip_root=True)
        self.assertFalse(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "file1")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "folder", "file2")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "file3")))

    def test_invalid_flat(self):
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            # Not a single dir containing everything
            file1 = os.path.join(tmp_folder, "subfolder-1.2.3", "folder2", "file1")
            file2 = os.path.join(tmp_folder, "other-1.2.3", "folder", "file2")

            save(file1, "")
            save(file2, "")

        zip_folder = temp_folder()
        zip_file = os.path.join(zip_folder, "file.zip")
        zipdir(tmp_folder, zip_file)

        # Extract without the subfolder
        extract_folder = temp_folder()
        with six.assertRaisesRegex(self, ConanException, "The zip file contains more than 1 folder "
                                                         "in the root"):
            unzip(zip_file, destination=extract_folder, strip_root=True)

    def test_invalid_flat_single_file(self):
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            save("file1", "contentsfile1")

        zip_folder = temp_folder()
        zip_file = os.path.join(zip_folder, "file.zip")
        zipdir(tmp_folder, zip_file)

        # Extract without the subfolder
        extract_folder = temp_folder()
        with six.assertRaisesRegex(self, ConanException, "The zip file contains a file in the root"):
            unzip(zip_file, destination=extract_folder, strip_root=True)


class TarExtractPlainTest(unittest.TestCase):

    def _compress_folder(self, folder, tgz_path):
        # Create a tar.gz file with the files in the folder
        with open(tgz_path, "wb") as tgz_handle:
            tgz = gzopen_without_timestamps("name", mode="w", fileobj=tgz_handle)

            files, _ = gather_files(folder)
            for filename, abs_path in files.items():
                info = tarfile.TarInfo(name=filename)
                with open(os.path.join(folder, filename), 'rb') as file_handler:
                    tgz.addfile(tarinfo=info, fileobj=file_handler)
            tgz.close()

    def test_plain_tgz(self):

        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            # Create a couple of files
            ori_files_dir = os.path.join(tmp_folder, "subfolder-1.2.3")
            file1 = os.path.join(ori_files_dir, "file1")
            file2 = os.path.join(ori_files_dir, "folder", "file2")
            file3 = os.path.join(ori_files_dir, "file3")

            save(file1, "")
            save(file2, "")
            save(file3, "")

        tgz_folder = temp_folder()
        tgz_file = os.path.join(tgz_folder, "file.tar.gz")
        self._compress_folder(tmp_folder, tgz_file)

        # Tgz unzipped regularly
        extract_folder = temp_folder()
        untargz(tgz_file, destination=extract_folder, strip_root=False)
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "file1")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "folder",
                                                    "file2")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "file3")))

        # Extract without the subfolder
        extract_folder = temp_folder()
        untargz(tgz_file, destination=extract_folder, strip_root=True)
        self.assertFalse(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "file1")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "folder", "file2")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "file3")))

    def test_plain_tgz_common_base(self):

        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            # Create a couple of files
            ori_files_dir = os.path.join(tmp_folder, "subfolder-1.2.3")
            file1 = os.path.join(ori_files_dir, "folder", "file1")
            file2 = os.path.join(ori_files_dir, "folder", "file2")
            file3 = os.path.join(ori_files_dir, "folder", "file3")

            save(file1, "")
            save(file2, "")
            save(file3, "")

        tgz_folder = temp_folder()
        tgz_file = os.path.join(tgz_folder, "file.tar.gz")
        self._compress_folder(tmp_folder, tgz_file)

        # Tgz unzipped regularly
        extract_folder = temp_folder()
        untargz(tgz_file, destination=extract_folder, strip_root=True)
        self.assertFalse(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "folder", "file1")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "folder", "file2")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "folder", "file3")))

    def test_invalid_flat(self):
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            # Not a single dir containing everything
            file1 = os.path.join(tmp_folder, "subfolder-1.2.3", "folder2", "file1")
            file2 = os.path.join(tmp_folder, "other-1.2.3", "folder", "file2")

            save(file1, "")
            save(file2, "")

        tgz_folder = temp_folder()
        tgz_file = os.path.join(tgz_folder, "file.tar.gz")
        self._compress_folder(tmp_folder, tgz_file)

        extract_folder = temp_folder()
        with six.assertRaisesRegex(self, ConanException, "The tgz file contains more than 1 folder "
                                                         "in the root"):
            untargz(tgz_file, destination=extract_folder, strip_root=True)

    def test_invalid_flat_single_file(self):
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            save("file1", "contentsfile1")

        zip_folder = temp_folder()
        tgz_file = os.path.join(zip_folder, "file.tar.gz")
        self._compress_folder(tmp_folder, tgz_file)

        # Extract without the subfolder
        extract_folder = temp_folder()
        with six.assertRaisesRegex(self, ConanException, "The tgz file contains a file in the root"):
            unzip(tgz_file, destination=extract_folder, strip_root=True)
