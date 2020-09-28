import abc
import ctypes
import os
import random
import six
import stat
import string
import sys
import tarfile
import time
import uuid
import zipfile

import unittest
from nose.plugins.attrib import attr
from parameterized import parameterized_class

from conans.client.tools.files import chdir, load
from conans.util.files import md5sum
from conans.test.utils.tools import TestClient


@six.add_metaclass(abc.ABCMeta)
class Compressor:
    @abc.abstractmethod
    def compress(self, d):
        raise NotImplementedError()

    @abc.abstractmethod
    def decompress(self, d):
        raise NotImplementedError()


class ZipCompressor(Compressor):
    ext = ".zip"

    def compress(self, d):
        def symlink_zipinfo(name):
            zi = zipfile.ZipInfo(name)
            # external_attr is 4 bytes in size
            # top 4 bits are for file type, 4 bits for setuid/setguid, then 16 bits for permissions
            # low order byte is MS-DOS directory attribute
            # 0xA000 (or 0120000 octal) is traditional value for symbolic link file type (S_IFLNK)
            # see also https://trac.edgewall.org/attachment/ticket/8919/ZipDownload.patch
            permissions = 0xA000
            zi.create_system = 3
            zi.external_attr = permissions << 16
            return zi

        with zipfile.ZipFile(file='test' + self.ext, mode='w', compression=zipfile.ZIP_DEFLATED) as f:
            for root, dirnames, filenames in os.walk(d):
                for filename in filenames:
                    filename = os.path.join(root, filename)
                    archname = os.path.relpath(filename, d)
                    if os.path.islink(filename):
                        target = os.readlink(filename)
                        f.writestr(symlink_zipinfo(archname), target)
                    else:
                        f.write(filename, archname)
                for dirname in dirnames:
                    filename = os.path.join(root, dirname)
                    archname = os.path.relpath(filename, d)
                    if os.path.islink(filename):
                        target = os.readlink(filename)
                        f.writestr(symlink_zipinfo(archname), target)
                    else:
                        f.write(filename, archname)
            f.close()

    def decompress(self, d):
        with zipfile.ZipFile(file='test' + self.ext, mode='r') as f:
            for zi in f.infolist():
                # type 4 bits are for file type, 0xA is for S_IFLNK (symbolic link)
                if (zi.external_attr >> 28) == 0xA:
                    f.extract(zi, path=d)
                    dst_name = os.path.join(d, zi.filename)
                    data = load(dst_name)
                    os.unlink(dst_name)
                    os.symlink(data, dst_name)
                else:
                    f.extract(zi, path=d)
                    dt = time.mktime(zi.date_time + (0, 0, -1))
                    os.utime(os.path.join(d, zi.filename), (dt, dt))
                    if os.name == 'posix':
                        permissions = zi.external_attr >> 16
                        os.chmod(os.path.join(d, zi.filename), permissions)
            f.close()


class TarCompressor(Compressor):
    read_mode = "r"
    write_mode = "w"
    ext = ".tar"

    def compress(self, d):
        with tarfile.open(name='test' + self.ext, mode=self.write_mode, format=tarfile.GNU_FORMAT) as f:
            inodes = dict()
            for root, dirnames, filenames in os.walk(d):
                for filename in filenames:
                    filename = os.path.join(root, filename)
                    archname = os.path.relpath(filename, d)

                    ti = tarfile.TarInfo(archname)
                    if os.path.islink(filename):
                        ti.type = tarfile.SYMTYPE
                        ti.linkname = os.readlink(filename)
                        ti.size = 0
                        f.addfile(tarinfo=ti)
                    else:
                        st = os.stat(filename)
                        if st.st_ino in inodes:
                            ti.type = tarfile.LNKTYPE
                            ti.linkname = inodes[st.st_ino]
                            ti.size = 0
                            ti.mode = st.st_mode
                            ti.mtime = st.st_mtime
                            f.addfile(tarinfo=ti)
                        else:
                            inodes[st.st_ino] = archname
                            ti.size = st.st_size
                            ti.mode = st.st_mode
                            ti.mtime = st.st_mtime
                            with open(filename, 'rb') as file_handler:
                                f.addfile(tarinfo=ti, fileobj=file_handler)
                for dirname in dirnames:
                    filename = os.path.join(root, dirname)
                    archname = os.path.relpath(filename, d)
                    ti = tarfile.TarInfo(archname)
                    if os.path.islink(filename):
                        ti.type = tarfile.SYMTYPE
                        ti.linkname = os.readlink(filename)
                        ti.size = 0
                        f.addfile(tarinfo=ti)
                    else:
                        st = os.stat(filename)
                        ti.type = tarfile.DIRTYPE
                        ti.size = 0
                        ti.mode = st.st_mode
                        f.addfile(tarinfo=ti)

            f.close()

    def decompress(self, d):
        import tarfile
        with tarfile.open(name='test' + self.ext, mode=self.read_mode) as f:
            f.extractall(path=d)
            f.close()

class TarGzCompressor(TarCompressor):
    read_mode = "r:gz"
    write_mode = "w:gz"
    ext = ".tgz"


class TarBz2Compressor(TarCompressor):
    read_mode = "r:bz2"
    write_mode = "w:bz2"
    ext = ".tbz2"


class TarLZMACompressor(TarCompressor):
    read_mode = "r:xz"
    write_mode = "w:xz"
    ext = ".txz"


compressors = [{"compressor": ZipCompressor()},
               {"compressor": TarCompressor()},
               {"compressor": TarGzCompressor()},
               {"compressor": TarBz2Compressor()}]

if sys.version_info.major >= 3:
    compressors.append({"compressor": TarLZMACompressor()})


# check if we can actually support symlinks:
# some operation systems might not support them
# e.g. Windows 10 requires either privileges or developer mode
# also only certain file systems have support (e.g. NTFS does, but FAT32 doesn't)
def symlinks_supported():
    if not hasattr(os, "symlink"):
        return False
    client = TestClient()
    try:
        client.save({"a": ""})
        with chdir(client.current_folder):
            os.symlink("a", "b")
            return os.path.islink("b")
    except OSError:
        return False


def hardlinks_supported():
    if not hasattr(os, "link"):
        return False
    client = TestClient()
    try:
        client.save({"a": ""})
        with chdir(client.current_folder):
            os.link("a", "b")
            return os.stat("a").st_ino == os.stat("b").st_ino
    except OSError:
        return False


@parameterized_class(compressors)
@attr("slow")
class CompressionTest(unittest.TestCase):
    @classmethod
    def get_file_list(cls, d):
        files = []
        dirs = []
        links = []
        for root, dirnames, filenames in os.walk(d):
            for filename in filenames:
                relpath = os.path.relpath(os.path.join(root, filename), d)
                if os.path.islink(os.path.join(root, filename)):
                    links.append(relpath)
                else:
                    files.append(relpath)
            for dirname in dirnames:
                relpath = os.path.relpath(os.path.join(root, dirname), d)
                if os.path.islink(os.path.join(root, dirname)):
                    links.append(relpath)
                else:
                    dirs.append(relpath)
        return files, dirs, links

    @classmethod
    def is_broken_link(cls, link):
        if os.path.islink(link):
            target = os.readlink(link)
            return not os.path.exists(target)
        return False

    @classmethod
    def get_inodes(cls, d, files):
        inodes = dict()
        for filename in files:
            stat = os.stat(os.path.join(d, filename))
            if stat.st_ino not in inodes:
                inodes[stat.st_ino] = []
            inodes[stat.st_ino].append(filename)
        return sorted(list(inodes.values()))

    def compare_dirs(self, d1, d2):
        files1, dirs1, links1 = self.get_file_list(d1)
        files2, dirs2, links2 = self.get_file_list(d2)
        self.assertEqual(files1, files2)
        self.assertEqual(dirs1, dirs2)
        self.assertEqual(links1, links2)

        for link in links1:
            filename1 = os.path.join(d1, link)
            filename2 = os.path.join(d2, link)

            self.assertTrue(os.path.islink(filename2))
            target1 = os.readlink(filename1)
            target2 = os.readlink(filename2)
            self.assertEqual(target1, target2)

            self.assertEqual(self.is_broken_link(filename1), self.is_broken_link(filename2))

        for filename in files1:
            filename1 = os.path.join(d1, filename)
            filename2 = os.path.join(d2, filename)

            # don't try to run on symlinks - they might be broken!
            stat1 = os.stat(filename1)
            stat2 = os.stat(filename2)
            self.assertEqual(stat1.st_size, stat2.st_size)
            # 1. verify contents
            self.assertEqual(md5sum(filename1), md5sum(filename2))
            # 2. verify timestamps
            t1 = int(stat1.st_mtime)
            t2 = int(stat2.st_mtime)
            if isinstance(self.compressor, ZipCompressor):
                # ZIP: The date and time are encoded in standard MS-DOS format.
                # MS-DOS uses year values relative to 1980 and 2 second precision.
                t1 &= ~1
                t2 &= ~1
            self.assertEqual(t1, t2)
            # 3. verify permissions
            self.assertEqual(stat.S_IMODE(stat1.st_mode), stat.S_IMODE(stat2.st_mode))

        # compare I-nodes for hard-links
        inodes1 = self.get_inodes(d1, files1)
        inodes2 = self.get_inodes(d2, files2)
        self.assertEqual(inodes1, inodes2)

    @classmethod
    def gen_n_chars(cls, length):
        return ''.join([random.choice(string.ascii_letters + string.digits) for _ in range(length)])

    @classmethod
    def gen_filename(cls, level=0):
        filename = str(uuid.uuid4())
        ext = cls.gen_n_chars(3)
        components = [cls.gen_n_chars(8) for _ in range(level)]
        components.append(filename + "." + ext)
        return os.path.join(*components)

    def gen_files(self, client, count=1, level=1, filesize=1024):
        files = dict()
        for i in range(count):
            files[self.gen_filename(level=level)] = self.gen_n_chars(filesize)
        client.save(files, clean_first=True)

        # generate timestamps on files
        for filename in files.keys():
            # ZIP doesn't support timestamps before 1980
            time1980 = time.mktime((1980, 1, 1, 0, 0, 0, 0, 0, 0))
            atime = random.randrange(time1980, 1 << 32)
            mtime = random.randrange(time1980, 1 << 32)
            os.utime(os.path.join(client.current_folder, filename), (atime, mtime))

            if os.name == 'posix':
                permission = random.randrange(0, 0o777)
                # at least read permission is needed to archive
                permission |= stat.S_IROTH | stat.S_IRUSR
                os.chmod(os.path.join(client.current_folder, filename), permission)

        return files

    def setUp(self):
        # common for all tests below
        self.c1 = TestClient()
        self.c2 = TestClient()

    def compress_decompress_check(self):
        # common for all tests below
        self.compressor.compress(self.c1.current_folder)
        self.compressor.decompress(self.c2.current_folder)

        self.compare_dirs(self.c1.current_folder, self.c2.current_folder)

    def test_basic(self):
        self.c1.save(self.gen_files(client=self.c1, count=10, level=3, filesize=10*1024),
                     clean_first=True)

        self.compress_decompress_check()

    # simple valid file symbolic link
    @unittest.skipUnless(symlinks_supported(), "requires symlinks")
    def test_simple_file_symlink(self):
        files = self.gen_files(client=self.c1)

        with chdir(self.c1.current_folder):
            os.symlink(list(files.keys())[0], self.gen_filename())

        self.compress_decompress_check()

    # simple valid directory symbolic link
    @unittest.skipUnless(symlinks_supported(), "requires symlinks")
    def test_simple_dir_symlink(self):
        files = self.gen_files(client=self.c1)

        with chdir(self.c1.current_folder):
            filename = list(files.keys())[0]
            dirname = os.path.dirname(filename)
            os.symlink(dirname, self.gen_filename())

        self.compress_decompress_check()

    # simple valid file symbolic link (absolute)
    @unittest.skipUnless(symlinks_supported(), "requires symlinks")
    def test_abs_symlink(self):
        files = self.gen_files(client=self.c1)

        with chdir(self.c1.current_folder):
            os.symlink(os.path.abspath(list(files.keys())[0]), self.gen_filename())

        self.compress_decompress_check()

    # valid relative symbolic link to the parent directory like "../A/B"
    @unittest.skipUnless(symlinks_supported(), "requires symlinks")
    def test_relative_symlink(self):
        files = self.gen_files(client=self.c1, count=2)

        with chdir(self.c1.current_folder):
            a = list(files.keys())[0]
            b = list(files.keys())[1]
            os.unlink(b)
            os.symlink(os.path.relpath(a, os.path.dirname(b)) ,b)

        self.compress_decompress_check()

    # symbolic link pointing to the non-existing file
    @unittest.skipUnless(symlinks_supported(), "requires symlinks")
    def test_broken_symlink(self):
        with chdir(self.c1.current_folder):
            os.symlink(self.gen_filename(), self.gen_filename())

        self.compress_decompress_check()

    # symbolink link pointing outside of the archive (e.g. system location like "/dev/null")
    @unittest.skipUnless(symlinks_supported(), "requires symlinks")
    def test_symlink_outside(self):
        self.c3 = TestClient()
        files = self.gen_files(client=self.c3)

        with chdir(self.c1.current_folder):
            os.symlink(os.path.join(self.c3.current_folder, list(files.keys())[0]),
                       self.gen_filename())

        self.compress_decompress_check()

    # cyclic reference A -> B, B -> A
    @unittest.skipUnless(symlinks_supported(), "requires symlinks")
    def test_cyclic_symlink(self):
        with chdir(self.c1.current_folder):
            a = self.gen_filename()
            b = self.gen_filename()
            os.symlink(a, b)
            os.symlink(b, a)

        self.compress_decompress_check()

    # transitive A -> B -> C
    @unittest.skipUnless(symlinks_supported(), "requires symlinks")
    def test_transitive_symlinks(self):
        files = self.gen_files(client=self.c1)
        with chdir(self.c1.current_folder):
            a = list(files.keys())[0]
            b = self.gen_filename()
            c = self.gen_filename()
            os.symlink(a, b)
            os.symlink(b, c)

        self.compress_decompress_check()

    # check the empty directory and symlink to the empty directory
    @unittest.skipUnless(symlinks_supported(), "requires symlinks")
    def test_empty_directory(self):
        self.gen_files(client=self.c1)
        with chdir(self.c1.current_folder):
            a = self.gen_filename()
            b = self.gen_filename()
            os.makedirs(a)
            os.symlink(a, b)

        self.compress_decompress_check()

    # simple file hard-link
    @unittest.skipUnless(hardlinks_supported(), "requires hardlinks")
    def test_hardlink(self):
        if isinstance(self.compressor, ZipCompressor):
            # zip format doesn't seem to support hard-links?
            return
        files = self.gen_files(client=self.c1, count=2)

        with chdir(self.c1.current_folder):
            a = list(files.keys())[0]
            b = list(files.keys())[1]
            os.unlink(b)
            os.link(a, b)

        self.compress_decompress_check()
