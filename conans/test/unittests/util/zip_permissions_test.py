import os
import platform
import stat
import zipfile
from os.path import basename
from unittest import TestCase

from six import StringIO

from conans.client.output import ConanOutput
from conans.client.tools.files import unzip
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class ZipPermissionsTest(TestCase):

    def test_permissions(self):
        if platform.system() != "Windows":
            for keep_permissions in [True, False]:
                for perm_set in [stat.S_IRWXU, stat.S_IRUSR]:
                    tmp_dir = temp_folder()
                    file_path = os.path.join(tmp_dir, "a_file.txt")
                    save(file_path, "contents")
                    os.chmod(file_path, perm_set)
                    zf = zipfile.ZipFile(os.path.join(tmp_dir, 'zipfile.zip'), mode='w')
                    zf.write(file_path, basename(file_path))
                    zf.close()

                    # Unzip and check permissions are kept
                    dest_dir = temp_folder()
                    unzip(os.path.join(tmp_dir, 'zipfile.zip'), dest_dir,
                          keep_permissions=keep_permissions, output=ConanOutput(StringIO()))

                    dest_file = os.path.join(dest_dir, "a_file.txt")
                    if keep_permissions:
                        self.assertEqual(stat.S_IMODE(os.stat(dest_file).st_mode), perm_set)
                    else:
                        self.assertNotEqual(stat.S_IMODE(os.stat(dest_file).st_mode), perm_set)
