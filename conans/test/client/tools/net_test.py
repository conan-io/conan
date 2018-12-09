# coding=utf-8

import unittest
import os

from conans.client.tools import net


class ToolsNetTest(unittest.TestCase):

    test_file_name = "readme.txt"

    def tearDown(self):
        os.remove(self.test_file_name)

    def test_ftp_auth(self):
        net.ftp_download("test.rebex.net", self.test_file_name, "demo", "password")

