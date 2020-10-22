import os
import unittest

import six

from conans.client.tools.files import check_md5, check_sha1, check_sha256
from conans.errors import ConanException
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class HashesTest(unittest.TestCase):

    def test_md5(self):
        folder = temp_folder()
        filepath = os.path.join(folder, "file.txt")
        file_content = "a file"
        save(filepath, file_content)

        check_md5(filepath, "d6d0c756fb8abfb33e652a20e85b70bc")
        check_sha1(filepath, "eb599ec83d383f0f25691c184f656d40384f9435")
        check_sha256(filepath, "7365d029861e32c521f8089b00a6fb32daf0615025b69b599d1ce53501b845c2")

        with six.assertRaisesRegex(self, ConanException, "md5 signature failed for 'file.txt' file."):
            check_md5(filepath, "invalid")

        with six.assertRaisesRegex(self, ConanException, "sha1 signature failed for 'file.txt' file."):
            check_sha1(filepath, "invalid")

        with six.assertRaisesRegex(self, ConanException, "sha256 signature failed for 'file.txt' file."):
            check_sha256(filepath, "invalid")
