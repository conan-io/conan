import os
import shutil
import unittest
import zipfile

from conans.client.tools.files import chdir, unzip
from conans.test.utils.test_files import temp_folder
from conans.util.files import save_files, save, md5sum

# check if we can actually support symlinks:
# some operation systems might not support them
# e.g. Windows 10 requires either privileges or developer mode
# also only certain file systems have support (e.g. NTFS does, but FAT32 doesn't)
def symlinks_supported():
    if not hasattr(os, "symlink"):
        return False
    tmpdir = temp_folder()
    try:
        save_files(tmpdir, {"a": ""})
        with chdir(tmpdir):
            os.symlink("a", "b")
            return os.path.islink("b")
    except OSError:
        return False
    finally:
        shutil.rmtree(tmpdir)

class ZipSymLinksTest(unittest.TestCase):
    @unittest.skipUnless(symlinks_supported(), "requires symlinks")
    def test_symlinks(self):
        tmpdir = temp_folder()

        a = os.path.join(tmpdir, "a_file.txt")
        b = os.path.join(tmpdir, "b_file.txt")
        save(a, "contents")
        os.symlink(os.path.relpath(a, os.path.dirname(b)), b)

        zipname = os.path.join(tmpdir, 'zipfile.zip')
        with zipfile.ZipFile(zipname, mode='w') as zf:
            zf.write(a, os.path.basename(a))

            zi = zipfile.ZipInfo(os.path.basename(b))
            target = os.readlink(b)
            permissions = 0xA000
            zi.create_system = 3
            zi.external_attr = permissions << 16
            zf.writestr(zi, target)

        dst = temp_folder()
        unzip(zipname, dst)

        a = os.path.join(dst, "a_file.txt")
        b = os.path.join(dst, "b_file.txt")

        self.assertEqual(md5sum(a), md5sum(b))

        self.assertTrue(os.path.islink(b))
        self.assertEqual(os.readlink(b), os.path.relpath(a, os.path.dirname(b)))
