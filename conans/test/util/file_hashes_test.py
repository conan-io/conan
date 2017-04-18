import unittest

from conans.tools import check_md5, check_sha256, check_sha1
from conans.test.utils.test_files import temp_folder
from conans.util.files import save
import os
from conans.errors import ConanException


class HashesTest(unittest.TestCase):

    def md5_test(self):
        folder = temp_folder()
        filepath = os.path.join(folder, "file.txt")
        file_content = "a file"
        save(filepath, file_content)

        check_md5(filepath, "d6d0c756fb8abfb33e652a20e85b70bc")
        check_sha1(filepath, "eb599ec83d383f0f25691c184f656d40384f9435")
        check_sha256(filepath, "7365d029861e32c521f8089b00a6fb32daf0615025b69b599d1ce53501b845c2")

        with self.assertRaisesRegexp(ConanException, "md5 signature failed for 'file.txt' file. Computed signature:"):
            check_md5(filepath, "invalid")

        with self.assertRaisesRegexp(ConanException, "sha1 signature failed for 'file.txt' file. Computed signature:"):
            check_sha1(filepath, "invalid")

        with self.assertRaisesRegexp(ConanException, "sha256 signature failed for 'file.txt' file. Computed signature:"):
            check_sha256(filepath, "invalid")
