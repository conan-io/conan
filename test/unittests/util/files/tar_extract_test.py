import os
import platform
import tarfile
import pytest

from conan.internal.api.uploader import gzopen_without_timestamps
from conan.test.utils.test_files import temp_folder
from conan.internal.util.files import tar_extract, save, gather_files, chdir


class TestTarExtract:

    @pytest.fixture
    def setup_files(self):
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            # Create a couple of files
            ori_files_dir = os.path.join(tmp_folder, "ori")
            file1 = os.path.join(ori_files_dir, "file1")
            file2 = os.path.join(ori_files_dir, "folder", "file2")
            save(file1, "")
            save(file2, "")

            # Create a tar.gz file with the above files
            tgz_file = os.path.join(tmp_folder, "file.tar.gz")
            with open(tgz_file, "wb") as tgz_handle:
                tgz = gzopen_without_timestamps("name", fileobj=tgz_handle)

                files, _ = gather_files(ori_files_dir)
                for filename, abs_path in files.items():
                    info = tarfile.TarInfo(name=filename)
                    with open(file1, 'rb') as file_handler:
                        tgz.addfile(tarinfo=info, fileobj=file_handler)
                tgz.close()
        return tmp_folder, tgz_file

    @pytest.mark.skipif(platform.system() == "Windows", reason="Requires Linux or Mac")
    def test_link_folder(self, setup_files):
        # If there is a linked folder in the current directory that matches one file in the tar.
        # https://github.com/conan-io/conan/issues/4959
        tmp_folder, tgz_file = setup_files

        # Once unpackaged, this is the content of the destination directory
        def check_files(destination_dir):
            d = sorted(os.listdir(destination_dir))
            assert d == ["file1", "folder"]
            d_folder = os.listdir(os.path.join(destination_dir, "folder"))
            assert d_folder == ["file2"]

        working_dir = temp_folder()
        with chdir(working_dir):
            # Unpack and check
            destination_dir = os.path.join(tmp_folder, "dest")
            with open(tgz_file, 'rb') as file_handler:
                tar_extract(file_handler, destination_dir)
            check_files(destination_dir)

            # Unpack and check (now we have a symlinked local folder)
            os.symlink(temp_folder(), "folder")
            destination_dir = os.path.join(tmp_folder, "dest2")
            with open(tgz_file, 'rb') as file_handler:
                tar_extract(file_handler, destination_dir)
            check_files(destination_dir)
