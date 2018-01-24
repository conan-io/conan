import unittest
import os
from conans.client.printer import Printer
from conans.client.deps_builder import DepsGraph, Node, DepsGraphBuilder
from conans.client.remote_registry import RemoteRegistry
from conans.test.utils.tools import TestClient, TestBufferConanOutput, TestServer
from conans.test.utils.conanfile import TestConanFile
from conans.model.conan_file import create_requirements
from conans.client.loader import ConanFileLoader
from conans.test.model.transitive_reqs_test import Retriever
from conans.model.profile import Profile
from conans.model.settings import Settings


conanfile_libA = """
from conans import ConanFile

class AConan(ConanFile):
    name = "aaa"
    version = "0.1"
"""

conanfile_libB = """
from conans import ConanFile

class BConan(ConanFile):
    name = "bbb"
    version = "0.1"
    requires = "aaa/0.1@lasote/channel"
"""

conanfile_libC = """
from conans import ConanFile

class CConan(ConanFile):
    name = "ccc"
    version = "0.1"
    requires = "bbb/0.1@lasote/channel"
    exports = "txt_file.txt"

"""

txt_file = """
    example file
    """

class PrinterTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer([], users={"lasote": "mypass"})
        servers = {"default": test_server}

        self.client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        files = {"conanfile_libA.py": conanfile_libA,
                 "conanfile_libB.py": conanfile_libB,
                 "conanfile_libC.py": conanfile_libC,
                 "txt_file.txt": txt_file
                }
        self.client.save(files)
        self.client.run("export conanfile_libA.py lasote/channel")
        self.client.run("upload aaa/0.1@lasote/channel -r default")
        self.client.run("remove -f aaa/0.1@lasote/channel")
        self.client.run("export conanfile_libB.py lasote/channel")
        self.client.run("upload bbb/0.1@lasote/channel -r default")
        self.client.run("remove -f bbb/0.1@lasote/channel")
        self.client.run("export conanfile_libC.py lasote/channel")

    # def print_graph_test(self):
    #     self.client.run("install ccc/0.1@lasote/channel",
    #                ignore_error=True) #Ignore ERROR: Missing prebuilt package
    #     self.assertIn("aaa/0.1@lasote/channel from 'default'", self.client.out)
    #     self.assertIn("bbb/0.1@lasote/channel from 'default'", self.client.out)
    #     self.assertIn("ccc/0.1@lasote/channel from local cache", self.client.out)

    # def print_info_test(self):
    #     self.client.run("info aaa/0.1@lasote/channel")

    #     aaa_header_output = """aaa/0.1@lasote/channel
    # ID: 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9
    # BuildID: None
    # Remote: default=http://"""
    #     aaa_require_output = """Required by:
    #     None"""
    #     self.assertIn(aaa_header_output, self.client.out)
    #     self.assertIn(aaa_require_output, self.client.out)

    #     self.client.run("info bbb/0.1@lasote/channel")

    #     aaa_require_output = """Required by:
    #     bbb/0.1@lasote/channel"""
    #     bbb_header_output = """bbb/0.1@lasote/channel
    # ID: 05ee4abde05ceb090f7e3a61dd0444da30515355
    # BuildID: None
    # Remote: default=http://"""
    #     bbb_require_output = """Required by:
    #     None
    # Requires:
    #     aaa/0.1@lasote/channel"""
    #     self.assertIn(aaa_require_output, self.client.out)
    #     self.assertIn(bbb_header_output, self.client.out)
    #     self.assertIn(bbb_require_output, self.client.out)

    #     self.client.run("info ccc/0.1@lasote/channel")

    #     bbb_require_output = """Required by:
    #     ccc/0.1@lasote/channel
    # Requires:
    #     aaa/0.1@lasote/channel"""
    #     ccc_header_output = """ccc/0.1@lasote/channel
    # ID: 981e05a6766d23b321ba61cd8d473ca507fcfbdc
    # BuildID: None
    # Remote: None"""
    #     ccc_require_output = """Required by:
    #     None
    # Requires:
    #     bbb/0.1@lasote/channel"""
    #     self.assertIn(bbb_require_output, self.client.out)
    #     self.assertIn(ccc_header_output, self.client.out)
    #     self.assertIn(ccc_require_output, self.client.out)

    # def print_search_recipes_test(self):
    #     self.client.run("search wrong_pattern*")
    #     self.assertIn("There are no packages matching the 'wrong_pattern*' pattern",
    #                   self.client.out)

    #     self.client.run("search ccc*")
    #     self.assertIn("Existing package recipes:", self.client.out)
    #     self.assertIn("ccc/0.1@lasote/channel", self.client.out)

    def print_search_packages_test(self):
        self.client.run("search ccc/0.1@lasote/channel")
        self.assertIn("There are no packages for pattern 'ccc/0.1@lasote/channel'", self.client.out)

        self.client.run("search ccc/0.1@lasote/channel -q os=Windows")
        self.assertIn("There are no packages for reference 'ccc/0.1@lasote/channel' matching the "
                      "query 'os=Windows'", self.client.out)

        self.client.run("install ccc/0.1@lasote/channel --build")
        self.client.run("search ccc/0.1@lasote/channel")
        self.assertIn("Existing packages for recipe ccc/0.1@lasote/channel:", self.client.out)
        self.assertIn("Package ID: 981e05a6766d23b321ba61cd8d473ca507fcfbdc", self.client.out)
        self.assertIn("aaa/0.1@lasote/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                       self.client.out)
        self.assertIn("bbb/0.1@lasote/channel:05ee4abde05ceb090f7e3a61dd0444da30515355",
                       self.client.out)
        self.assertIn("Outdated from recipe: False", self.client.out)

    def print_profile(self):
        pass
