import os
from unittest import TestCase
import six
import unittest
import tarfile

from conans.test.utils.test_files import temp_folder
from conans.tools import unzip, save
from conans.util.files import load
from conans.errors import ConanException


class XZTest(TestCase):

    @unittest.skipUnless(six.PY3, "only Py3")
    def test(self):
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "a_file.txt")
        save(file_path, "my content!")
        txz = os.path.join(tmp_dir, "sample.tar.xz")
        with tarfile.open(txz, "w:xz") as tar:
            tar.add(file_path, "a_file.txt")

        dest_folder = temp_folder()
        unzip(txz, dest_folder)
        content = load(os.path.join(dest_folder, "a_file.txt"))
        self.assertEqual(content, "my content!")

    @unittest.skipUnless(six.PY2, "only Py2")
    def test_error_python2(self):
        with self.assertRaisesRegexp(ConanException, "XZ format not supported in Python 2"):
            dest_folder = temp_folder()
            unzip("somefile.tar.xz", dest_folder)
