import os
import platform
import tarfile
import zipfile

import pytest
import sys

from conan.internal.api.uploader import gzopen_without_timestamps
from conan.tools.files import load
from conan.tools.files.files import untargz, unzip
from conan.errors import ConanException
from conan.internal.model.manifest import gather_files
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.mocks import RedirectedTestOutput
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import redirect_output
from conan.internal.util.files import chdir, save
from conan.internal.util.files import rmdir


class TestZipExtractPlain:

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
        assert "ERROR: Error extract" not in output
        assert os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3"))
        assert os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "file1"))
        assert os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "folder",
                                           "file2"))
        assert os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "file3"))

        # Extract without the subfolder
        extract_folder = temp_folder()
        output = RedirectedTestOutput()
        with redirect_output(output):
            unzip(ConanFileMock(), zip_file, destination=extract_folder, strip_root=True)
        assert "ERROR: Error extract" not in output
        assert not os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3"))
        assert os.path.exists(os.path.join(extract_folder, "file1"))
        assert os.path.exists(os.path.join(extract_folder, "folder", "file2"))
        assert os.path.exists(os.path.join(extract_folder, "file3"))

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
        try:
            unzip(ConanFileMock(), zip_file, destination=extract_folder, strip_root=True)
            assert False, "Expected ConanException"
        except ConanException as e:
            assert "The zip file contains more than 1 folder in the root" in str(e)

    def test_invalid_flat_single_file(self):
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            save("file1", "contentsfile1")

        zip_folder = temp_folder()
        zip_file = os.path.join(zip_folder, "file.zip")
        self._zipdir(tmp_folder, zip_file)

        # Extract without the subfolder
        extract_folder = temp_folder()
        try:
            unzip(ConanFileMock(), zip_file, destination=extract_folder, strip_root=True)
            assert False, "Expected ConanException"
        except ConanException as e:
            assert "The zip file contains a file in the root" in str(e)


class TestTarExtractPlain:

    def _compress_folder(self, folder, tgz_path, folder_entry=None):
        # Create a tar.gz file with the files in the folder and an additional TarInfo entry
        # for the folder_entry (the gather files doesn't return empty dirs)
        with open(tgz_path, "wb") as tgz_handle:
            tgz = gzopen_without_timestamps("name", fileobj=tgz_handle)
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
            tgz = gzopen_without_timestamps("name", fileobj=tgz_handle)

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
        assert os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3"))
        assert os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "file1"))
        assert os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "folder",
                                           "file2"))
        assert os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3", "file3"))

        # Extract without the subfolder
        extract_folder = temp_folder()
        untargz(tgz_file, destination=extract_folder, strip_root=True)
        assert not os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3"))
        assert os.path.exists(os.path.join(extract_folder, "file1"))
        assert os.path.exists(os.path.join(extract_folder, "folder", "file2"))
        assert os.path.exists(os.path.join(extract_folder, "file3"))

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
        assert not os.path.exists(os.path.join(extract_folder, "subfolder-1.2.3"))
        assert os.path.exists(os.path.join(extract_folder, "folder", "file1"))
        assert os.path.exists(os.path.join(extract_folder, "folder", "file2"))
        assert os.path.exists(os.path.join(extract_folder, "folder", "file3"))

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
        try:
            untargz(tgz_file, destination=extract_folder, strip_root=True)
            assert False, "Expected ConanException"
        except ConanException as e:
            assert "The tgz file contains more than 1 folder in the root" in str(e)

    def test_invalid_flat_single_file(self):
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            save("file1", "contentsfile1")

        zip_folder = temp_folder()
        tgz_file = os.path.join(zip_folder, "file.tar.gz")
        self._compress_folder(tmp_folder, tgz_file)

        # Extract without the subfolder
        extract_folder = temp_folder()
        try:
            unzip(ConanFileMock(), tgz_file, destination=extract_folder, strip_root=True)
            assert False, "Expected ConanException"
        except ConanException as e:
            assert "Can't untar a tgz containing files in the root with strip_root enabled" in str(e)

    def test_invalid_flat_multiple_file(self):
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            save("file1", "contentsfile1")
            save("file2", "contentsfile2")

        zip_folder = temp_folder()
        tgz_file = os.path.join(zip_folder, "file.tar.gz")
        self._compress_folder(tmp_folder, tgz_file)

        # Extract without the subfolder
        extract_folder = temp_folder()
        try:
            unzip(ConanFileMock(), tgz_file, destination=extract_folder, strip_root=True)
            assert False, "Expected ConanException"
        except ConanException as e:
            assert "Can't untar a tgz containing files in the root with strip_root enabled" in str(e)


def _compress_root_folder(folder, tgz_path, root_folder_name="root"):
    """
    Compress the whole folder adding withing the tar file also the folders. For instance:

    $ tar -tf '/tmp/folder/file.tar.gz'
    root/
    root/parent/
    root/parent/bin/
    root/parent/bin/file1
    root/parent/bin/file2
    """
    with open(tgz_path, "wb") as tgz_handle:
        tgz = gzopen_without_timestamps("name", fileobj=tgz_handle)
        files, _ = gather_files(folder)
        tgz.add(root_folder_name, arcname=os.path.basename(root_folder_name))
        tgz.close()


def test_decompressing_folders_with_different_modes():
    """
    When compressed folders come with restrictive permissions, untar() function should not
    raise a PermissionError.

    Issue related: https://github.com/conan-io/conan/issues/17987
    """
    tmp_folder = temp_folder()
    tgz_folder = temp_folder()
    tgz_file = os.path.join(tgz_folder, "file.tar.gz")
    with chdir(tmp_folder):
        save("root/parent/bin/file1", "contentsfile1")
        save("root/parent/bin/file2", "contentsfile2")
        os.chmod(os.path.join("root", "parent"), mode=0o555)
        os.chmod(os.path.join("root", "parent", "bin"), mode=0o700)
        _compress_root_folder(tmp_folder, tgz_file, root_folder_name="root")

    # Tgz unzipped regularly
    extract_folder = temp_folder()
    # Do not raise any PermissionError
    untargz(tgz_file, destination=extract_folder, strip_root=True)


@pytest.mark.skipif(sys.version_info < (3, 13, 4), reason="requires Python 3.13.4 or higher")
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_decompressing_using_long_path_prefix():
    """
    If we use the "\\?\" prefix, untar() function should not
    raise an OSError: [WinError 123] error.

    Issue related: https://github.com/conan-io/conan/issues/18574
    """
    tmp_folder = temp_folder()
    tgz_folder = temp_folder()
    tgz_file = os.path.join(tgz_folder, "file.tar.gz")
    with chdir(tmp_folder):
        save("root/parent/bin/file1", "contentsfile1")
        save("root/parent/bin/file2", "contentsfile2")
        _compress_root_folder(tmp_folder, tgz_file, root_folder_name="root")

    # Tgz unzipped regularly
    extract_folder = f"\\\\?\\{temp_folder()}"
    # Do not raise any OSError: [WinError 123]
    untargz(tgz_file, destination=extract_folder, strip_root=True)
    assert "contentsfile1" in load(ConanFileMock(), os.path.join(extract_folder, "parent", "bin", "file1"))
    assert "contentsfile2" in load(ConanFileMock(), os.path.join(extract_folder, "parent", "bin", "file2"))
    untargz(tgz_file, destination=extract_folder, strip_root=False)
    assert "contentsfile1" in load(ConanFileMock(), os.path.join(extract_folder, "root", "parent", "bin", "file1"))
    assert "contentsfile2" in load(ConanFileMock(), os.path.join(extract_folder, "root", "parent", "bin", "file2"))
