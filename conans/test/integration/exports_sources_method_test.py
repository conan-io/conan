import unittest
from collections import OrderedDict

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.test_files import scan_folder
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer

attribute_conanfile = """
from conans import ConanFile

class AttributeConan(ConanFile):
    name = "attribute"
    version = "0.1"
    exports_sources = "*.h"
"""

method_conanfile = """
from conans import ConanFile

class MethodConan(ConanFile):
    name = "method"
    version = "0.1"
    def export_sources(self):
        self.copy("*.h")
"""


class ExportsSourcesMethodTest(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.other_server = TestServer()
        servers = OrderedDict([("default", self.server),
                               ("other", self.other_server)])
        client1 = TestClient(servers=servers, users={"default": [("lasote", "mypass")],
                                                     "other": [("lasote", "mypass")]})
        self.client1 = client1
        self.ref1 = ConanFileReference.loads("attribute/0.1@")
        self.pref1 = PackageReference(self.ref1, NO_SETTINGS_PACKAGE_ID)
        self.source_folder1 = self.client1.cache.package_layout(self.ref1).source()
        self.export_sources_folder1 = self.client1.cache.package_layout(self.ref1).export_sources()

        client2 = TestClient(servers=servers, users={"default": [("lasote", "mypass")],
                                                     "other": [("lasote", "mypass")]})
        self.client2 = client2
        self.ref2 = ConanFileReference.loads("method/0.1@")
        self.pref2 = PackageReference(self.ref2, NO_SETTINGS_PACKAGE_ID)
        self.source_folder2 = self.client2.cache.package_layout(self.ref2).source()
        self.export_sources_folder2 = self.client2.cache.package_layout(self.ref2).export_sources()

    def method_matches_attribute_test(self):
        self._create_code(self.client1, attribute_conanfile)
        self.client1.run("export .")
        self.client1.run("create .")

        self._create_code(self.client2, method_conanfile)
        self.client2.run("export .")
        self.client2.run("create .")

        self._check_exports_sources_folder()
        self._check_source_folder()

    def _create_code(self, client, conanfile):
        client.save({"conanfile.py": conanfile, "src/hello.h": "hello"}, clean_first=True)

    def _check_exports_sources_folder(self):
        """ export_sources for attribute and method versions should match
        """
        expected_export_sources = sorted(["src/hello.h"])
        self.assertEqual(scan_folder(self.export_sources_folder1), expected_export_sources)
        self.assertEqual(scan_folder(self.export_sources_folder2), expected_export_sources)

    def _check_source_folder(self):
        """ source_folder for attribute and method versions should match
        """
        expected_sources = sorted(["src/hello.h"])
        self.assertEqual(scan_folder(self.source_folder1), expected_sources)
        self.assertEqual(scan_folder(self.source_folder2), expected_sources)
