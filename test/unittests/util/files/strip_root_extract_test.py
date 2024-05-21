import os
import tarfile
import unittest
import zipfile

from conan.tools.files.files import untargz, unzip
from conans.errors import ConanException
from conans.model.manifest import gather_files
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.mocks import RedirectedTestOutput
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import redirect_output
from conans.util.files import chdir, save
from conans.util.files import gzopen_without_timestamps, rmdir


class ZipExtractPlainTest(unittest.TestCase):

    def _zipdir(self, path, zipfilename, folder_entry=None):
        with zipfile.ZipFile(zipfilename, 'w', zipfile.ZIP_DEFLATED) as z:
            if folder_entry:
                zif = zipfile.ZipInfo(folder_entry + "/")
                z.writestr(zif, "")

            for root, _, files in os.walk(path):
                for f in files:
                    file_path = os.path.join(root, f)
                    if file_path == zipfilename:
                        continue
                    relpath = os.path.relpath(file_path, path)
                    z.write(file_path, relpath)

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
        # Zip with a "folder_entry" in the zip (not only for the files)
        self._zipdir(tmp_folder, zip_file, folder_entry="subfolder-1.2.3")

        # ZIP unzipped regularly
        extract_folder = temp_folder()
        output = RedirectedTestOutput()
        with redirect_output(output):
            unzip(ConanFileMock(), zip_file, destination=extract_folder, strip_root=False)
        self.assertNotIn("ERROR: Error extract", output)
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "file1")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "folder",
                                                    "file2")))
        self.assertTrue(os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "file3")))

        # Extract without the subfolder
        extract_folder = temp_folder()
        output = RedirectedTestOutput()
        with redirect_output(output):
            unzip(ConanFileMock(), zip_file, destination=extract_folder, strip_root=True)
        self.assertNotIn("ERROR: Error extract", output)
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
        self._zipdir(tmp_folder, zip_file)

        # Extract without the subfolder
        extract_folder = temp_folder()
        with self.assertRaisesRegex(ConanException, "The zip file contains more than 1 folder "
                                                         "in the root"):
            unzip(ConanFileMock(), zip_file, destination=extract_folder, strip_root=True)

    def test_invalid_flat_single_file(self):
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            save("file1", "contentsfile1")

        zip_folder = temp_folder()
        zip_file = os.path.join(zip_folder, "file.zip")
        self._zipdir(tmp_folder, zip_file)

        # Extract without the subfolder
        extract_folder = temp_folder()
        with self.assertRaisesRegex(ConanException, "The zip file contains a file in the root"):
            unzip(ConanFileMock(), zip_file, destination=extract_folder, strip_root=True)


class TarExtractPlainTest(unittest.TestCase):

    def _compress_folder(self, folder, tgz_path, folder_entry=None):
        # Create a tar.gz file with the files in the folder and an additional TarInfo entry
        # for the folder_entry (the gather files doesn't return empty dirs)
        with open(tgz_path, "wb") as tgz_handle:
            tgz = gzopen_without_timestamps("name", mode="w", fileobj=tgz_handle)
            if folder_entry:
                # Create an empty folder in the tgz file
                t = tarfile.TarInfo(folder_entry)
                t.mode = 488
                t.type = tarfile.DIRTYPE
                tgz.addfile(t)
            files, _ = gather_files(folder)
            for filename, abs_path in files.items():
                info = tarfile.TarInfo(name=filename)
                with open(os.path.join(folder, filename), 'rb') as file_handler:
                    tgz.addfile(tarinfo=info, fileobj=file_handler)
            tgz.close()

    def test_linkame_striproot_folder(self):
        tmp_folder = temp_folder()
        other_tmp_folder = temp_folder()
        save(os.path.join(other_tmp_folder, "foo.txt"), "")
        tgz_path = os.path.join(tmp_folder, "foo.tgz")

        with open(tgz_path, "wb") as tgz_handle:
            tgz = gzopen_without_timestamps("name", mode="w", fileobj=tgz_handle)

            # Regular file
            info = tarfile.TarInfo(name="common/foo.txt")
            info.name = "common/subfolder/foo.txt"
            info.path = "common/subfolder/foo.txt"
            with open(os.path.join(other_tmp_folder, "foo.txt"), 'rb') as file_handler:
                tgz.addfile(tarinfo=info, fileobj=file_handler)

            # A hardlink to the regular file
            info = tarfile.TarInfo(name="common/foo.txt")
            info.linkname = "common/subfolder/foo.txt"
            info.linkpath = "common/subfolder/foo.txt"
            info.name = "common/subfolder/bar/foo.txt"
            info.path = "common/subfolder/bar/foo.txt"
            info.type = b'1'  # This indicates a hardlink to the tgz file "common/subfolder/foo.txt"
            tgz.addfile(tarinfo=info, fileobj=None)
            tgz.close()

        assert not os.path.exists(os.path.join(tmp_folder, "subfolder", "foo.txt"))
        assert not os.path.exists(os.path.join(tmp_folder, "subfolder", "bar", "foo.txt"))
        untargz(tgz_path, destination=tmp_folder, strip_root=True)
        assert os.path.exists(os.path.join(tmp_folder, "subfolder", "foo.txt"))
        assert os.path.exists(os.path.join(tmp_folder, "subfolder", "bar", "foo.txt"))

        # Check develop2 public unzip
        rmdir(os.path.join(tmp_folder, "subfolder"))
        assert not os.path.exists(os.path.join(tmp_folder, "subfolder", "foo.txt"))
        assert not os.path.exists(os.path.join(tmp_folder, "subfolder", "bar", "foo.txt"))
        unzip(ConanFileMock(), tgz_path, destination=tmp_folder, strip_root=True)
        assert os.path.exists(os.path.join(tmp_folder, "subfolder", "foo.txt"))
        assert os.path.exists(os.path.join(tmp_folder, "subfolder", "bar", "foo.txt"))

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
        self._compress_folder(tmp_folder, tgz_file, folder_entry="subfolder-1.2.3")

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
        with self.assertRaisesRegex(ConanException, "The tgz file contains more than 1 folder "
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
        with self.assertRaisesRegex(ConanException, "The tgz file contains a file in the root"):
            unzip(ConanFileMock(), tgz_file, destination=extract_folder, strip_root=True)
