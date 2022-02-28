# coding=utf-8

import os
import shutil
import tempfile
import unittest

import pytest
import six

from conans.client.tools import chdir
from conans.client.tools import net
from conans.errors import ConanException


@pytest.mark.skip(msg="This causes more troubles than benefits, external ftp download is testing "
                      "very little conan code, mostly python")
class ToolsNetTest(unittest.TestCase):

    def run(self, *args, **kwargs):
        self.tmp_folder = tempfile.mkdtemp()
        try:
            with chdir(self.tmp_folder):
                super(ToolsNetTest, self).run(*args, **kwargs)
        finally:
            shutil.rmtree(self.tmp_folder)

    def test_ftp_auth(self):
        filename = "/pub/example/readme.txt"
        net.ftp_download("test.rebex.net", filename, "demo", "password")
        self.assertTrue(os.path.exists(os.path.basename(filename)))

    def test_ftp_invalid_path(self):
        with six.assertRaisesRegex(self, ConanException,
                                   "550 The system cannot find the file specified."):
            net.ftp_download("test.rebex.net", "invalid-file", "demo", "password")
        self.assertFalse(os.path.exists("invalid-file"))

    def test_ftp_invalid_auth(self):
        with six.assertRaisesRegex(self, ConanException, "530 User cannot log in."):
            net.ftp_download("test.rebex.net", "readme.txt", "demo", "invalid")
        self.assertFalse(os.path.exists("readme.txt"))
