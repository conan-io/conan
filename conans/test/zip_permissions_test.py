import os
import stat
import zipfile
from stat import ST_MODE
from unittest import TestCase

from os.path import basename

from conans import tools
from conans.test.utils.test_files import temp_folder
from conans.tools import unzip
from conans.util.files import save


class ZipPermissionsTest(TestCase):

    def test_permissions(self):
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "a_file.txt")
        save(file_path, "contents")
        os.chmod(file_path, stat.S_IRWXU)
        zf = zipfile.ZipFile(os.path.join(tmp_dir, 'zipfile.zip'), mode='w')
        zf.write(file_path, basename(file_path))
        zf.close()

        # Unzip and check permissions are kept
        dest_dir = temp_folder()
        unzip(os.path.join(tmp_dir, 'zipfile.zip'), dest_dir)

        dest_file = os.path.join(dest_dir, "a_file.txt")
        self.assertEquals(stat.S_IMODE(os.stat(dest_file).st_mode), stat.S_IRWXU)


