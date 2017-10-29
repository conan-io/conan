import unittest

from conans import tools
from conans.test.utils.test_files import temp_folder
import os
from conans.util.files import load


class ToolsDownloadTest(unittest.TestCase):

    def test_download(self):
        tmp_folder = temp_folder()
        with tools.chdir(tmp_folder):
            tools.download("https://raw.githubusercontent.com/conan-io/conan/develop/README.rst",
                           "README.rst")
            content = load(os.path.join(tmp_folder, "README.rst"))
            self.assertIn(":alt: Conan develop coverage", content)
