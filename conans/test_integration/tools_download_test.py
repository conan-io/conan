import unittest

from conans import tools
from conans.test.utils.test_files import temp_folder
import os
from conans.util.files import load


class ToolsDownloadTest(unittest.TestCase):

    def test_download_github_raw(self):
        tmp_folder = temp_folder()
        with tools.chdir(tmp_folder):
            tools.download("https://raw.githubusercontent.com/conan-io/conan/develop/README.rst",
                           "README.rst")
            content = load(os.path.join(tmp_folder, "README.rst"))
            self.assertIn(":alt: Conan develop coverage", content)

    def test_download_zip(self):
        tmp_folder = temp_folder()
        with tools.chdir(tmp_folder):
            tools.download("http://www.agentpp.com/download/snmp++-3.3.5.tar.gz",
                           "agenpro")
            tools.untargz("agenpro")
            content = load(os.path.join(tmp_folder, "snmp++-3.3.5/include/snmp_pp/vb.h"))
            self.assertIn("} // end of namespace Snmp_pp", content)

    def test_download_small_zip(self):
        tmp_folder = temp_folder()
        with tools.chdir(tmp_folder):
            tools.download("http://www.agentpp.com/download/vs2013.zip",
                           "agenpro")
            tools.unzip("agenpro")
            content = load(os.path.join(tmp_folder, "vs2013/AgentX++/include/config.h"))
            self.assertIn("/* define _SNMPv3 if you want to use SNMPv3 */", content)
