import os
import tarfile

from conan.tools.files import unzip
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.test_files import temp_folder
from conans.util.files import load, save


def test_unzip_can_xz():
    tmp_dir = temp_folder()
    file_path = os.path.join(tmp_dir, "a_file.txt")
    save(file_path, "my content!")
    txz = os.path.join(tmp_dir, "sample.tar.xz")
    with tarfile.open(txz, "w:xz") as tar:
        tar.add(file_path, "a_file.txt")

    dest_folder = temp_folder()
    unzip(ConanFileMock(), txz, dest_folder)
    content = load(os.path.join(dest_folder, "a_file.txt"))
    assert content == "my content!"

