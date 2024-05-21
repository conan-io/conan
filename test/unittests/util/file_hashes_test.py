import os
import unittest

from conan.tools.files import check_md5, check_sha1, check_sha256
from conans.errors import ConanException
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.test_files import temp_folder
from conans.util.files import save


class HashesTest(unittest.TestCase):

    def test_md5(self):
        folder = temp_folder()
        filepath = os.path.join(folder, "file.txt")
        file_content = "a file"
        save(filepath, file_content)

        check_md5(ConanFileMock(), filepath, "d6d0c756fb8abfb33e652a20e85b70bc")
        check_sha1(ConanFileMock(), filepath, "eb599ec83d383f0f25691c184f656d40384f9435")
        check_sha256(ConanFileMock(), filepath, "7365d029861e32c521f8089b00a6fb32daf0615025b69b599d1ce53501b845c2")

        with self.assertRaisesRegex(ConanException, "md5 signature failed for 'file.txt' file."):
            check_md5(ConanFileMock(), filepath, "invalid")

        with self.assertRaisesRegex(ConanException, "sha1 signature failed for 'file.txt' file."):
            check_sha1(ConanFileMock(), filepath, "invalid")

        with self.assertRaisesRegex(ConanException, "sha256 signature failed for 'file.txt' file."):
            check_sha256(ConanFileMock(), filepath, "invalid")
