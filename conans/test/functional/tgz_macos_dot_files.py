import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import unittest

from parameterized import parameterized

from conans.client.remote_manager import uncompress_file
from conans.test.utils.tools import TestBufferConanOutput


@unittest.skipUnless(platform.system() == "Darwin", "Requires OSX")
class TgzMacosDotFilesTest(unittest.TestCase):

    @parameterized.expand([(True, ), (False, )])
    def test_delete_dot_files(self, clean_macos_dot_files):
        tmp = tempfile.mkdtemp()
        try:
            src_folder = os.path.join(tmp, "src")
            os.makedirs(src_folder)

            actual_file = os.path.join(src_folder, "file.txt")
            files = [actual_file,
                     os.path.join(src_folder, "other.txt"),
                     os.path.join(src_folder, "._random.txt")]
            compressed_file = os.path.join(tmp, "z.tar.gz")

            # Compress all files, add meta-data to one of them
            for f in files:
                subprocess.check_output(["touch", f], stderr=subprocess.STDOUT)
            subprocess.check_output(["xattr", "-w", "name", "value", actual_file],
                                    stderr=subprocess.STDOUT)
            subprocess.check_output(["tar", "-zcvf", compressed_file, "-C", src_folder, "."],
                                    stderr=subprocess.STDOUT)

            # Check that the offending file is in place
            tar = tarfile.open(compressed_file)
            files = [item.name for item in tar.getmembers()]
            self.assertTrue(any('._file.txt' in it for it in files))
            self.assertTrue(any("other.txt" in it for it in files))
            self.assertFalse(any("._random.txt" in it for it in files))  # Macos ignores these

            # Uncompress
            output = TestBufferConanOutput()
            uncompress_file(src_path=compressed_file,
                            dest_folder=os.path.join(tmp, "dst"),
                            output=output,
                            clean_macos_dot_files=clean_macos_dot_files)
            files = os.listdir(os.path.join(tmp, "dst"))
            self.assertEquals(any("._" in it for it in files), not clean_macos_dot_files)
        finally:
            shutil.rmtree(tmp)
