# coding=utf-8

import os
import platform
import shutil
import tempfile
import unittest
import copy

import six

from conans.client.tools import chdir
from conans.client.tools import net
from conans.errors import ConanException
from conans.test.utils.tools import TestBufferConanOutput


class ToolsNetTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()

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

    # FIXME. This was removed cause failures in CI, but doesn't make sense to fail only on OSX
    @unittest.skipIf(platform.system() == "Darwin", "Fails in Macos")
    def test_ftp_anonymous(self):
        filename = "1KB.zip"
        net.ftp_download("speedtest.tele2.net", filename)
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

    def test_ftp_download_list(self):
        """ Must download only the first URL and ignore all mirrors """
        logins = ["demo"] * 3
        passwords = ["password"] * 3
        urls = ["test.rebex.net"] * 3
        filenames = ["/pub/example/" + it for it in ("readme.txt", "winceclient.png", "winceclientSmall.png")]
        net.ftp_download(urls, filenames, logins, passwords, self.output)
        self.assertTrue(os.path.exists(os.path.basename(filenames[0])))
        self.assertFalse(os.path.exists(os.path.basename(filenames[1])))
        self.assertFalse(os.path.exists(os.path.basename(filenames[2])))
        self.assertNotIn("Could not download", str(self.output))

    def test_ftp_download_from_mirror(self):
        """ Must download only the third URL and ignore the last one """
        logins = ["demo"] * 4
        passwords = ["password"] * 4
        urls = ["test.rebex.net"] * 4
        filenames = ["/pub/example/" + it for it in ("foobar.txt", "couse.png", "winceclientSmall.png", "mail-editor.png")]
        net.ftp_download(urls, copy.copy(filenames), logins, passwords, self.output)
        self.assertFalse(os.path.exists(os.path.basename(filenames[0])))
        self.assertFalse(os.path.exists(os.path.basename(filenames[1])))
        self.assertTrue(os.path.exists(os.path.basename(filenames[2])))
        self.assertFalse(os.path.exists(os.path.basename(filenames[3])))
        self.assertIn("WARN: Could not download the file foobar.txt from "
                      "test.rebex.net. Trying a new mirror.", str(self.output))
        self.assertIn("WARN: Could not download the file couse.png from "
                      "test.rebex.net. Trying a new mirror.", str(self.output))
        self.assertNotIn("winceclientSmall.png", str(self.output))
        self.assertNotIn("mail-editor.png", str(self.output))

    def test_ftp_download_error_mirror(self):
        """ Must fail to download all files """
        logins = ["demo"] * 4
        passwords = ["password"] * 4
        urls = ["test.rebex.net"] * 4
        filenames = ["/pub/example/" + it for it in ("foobar.txt", "couse.png", "qux.png", "blah.png")]
        with self.assertRaises(ConanException) as error:
            net.ftp_download(urls, copy.copy(filenames), logins, passwords, self.output)
        for filename in filenames:
            self.assertFalse(os.path.exists(os.path.basename(filename)))
            self.assertIn("WARN: Could not download the file", str(self.output))
            self.assertIn("Error in FTP download from test.rebex.net\n"
                          "550 The system cannot find the file specified.", str(error.exception))
