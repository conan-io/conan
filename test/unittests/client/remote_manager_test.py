import os

from conan.internal.api.uploader import compress_files
from conan.internal.paths import PACKAGE_TGZ_NAME, PACKAGE_TZSTD_NAME
from conan.internal.rest.remote_manager import uncompress_file
from conan.test.utils.test_files import temp_folder
from conan.internal.util.files import save


class TestRemoteManager:

    def test_compress_files_tgz(self):
        folder = temp_folder()
        save(os.path.join(folder, "one_file.txt"), "The contents")
        save(os.path.join(folder, "Two_file.txt"), "Two contents")

        files = {
            "one_file.txt": os.path.join(folder, "one_file.txt"),
            "Two_file.txt": os.path.join(folder, "Two_file.txt"),
        }

        path = compress_files(files, PACKAGE_TGZ_NAME, dest_dir=folder)
        assert os.path.exists(path)
        expected_path = os.path.join(folder, PACKAGE_TGZ_NAME)
        assert path == expected_path

    def test_compress_and_uncompress_zst_files(self):
        folder = temp_folder()
        save(os.path.join(folder, "one_file.txt"), "The contents")
        save(os.path.join(folder, "Two_file.txt"), "Two contents")

        files = {
            "one_file.txt": os.path.join(folder, "one_file.txt"),
            "Two_file.txt": os.path.join(folder, "Two_file.txt"),
        }

        path = compress_files(files, PACKAGE_TZSTD_NAME, dest_dir=folder, compressformat="zstd")
        assert os.path.exists(path)
        expected_path = os.path.join(folder, PACKAGE_TZSTD_NAME)
        assert path == expected_path

        extract_dir = os.path.join(folder, "extracted")
        uncompress_file(path, extract_dir)

        extract_files = list(sorted(os.listdir(extract_dir)))
        expected_files = sorted(files.keys())
        assert extract_files == expected_files

        for name, path in sorted(files.items()):
            extract_path = os.path.join(extract_dir, name)
            with open(path, "r") as f1, open(extract_path, "r") as f2:
                assert f1.read() == f2.read()
