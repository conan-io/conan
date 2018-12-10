# coding=utf-8

import unittest
import os

from conans.client.tools import net


class ToolsNetTest(unittest.TestCase):

    test_file_name_auth = "readme.txt"
    test_file_name_anonymous = "1KB.zip"

    def tearDown(self):

        if os.path.exists(self.test_file_name_auth):
            os.remove(self.test_file_name_auth)

        if os.path.exists(self.test_file_name_anonymous):
            os.remove(self.test_file_name_anonymous)

    def test_ftp_auth(self):
        net.ftp_download("test.rebex.net", self.test_file_name_auth, "demo", "password")

    def test_ftp_anonymous(self):
        net.ftp_download("speedtest.tele2.net", self.test_file_name_anonymous)
