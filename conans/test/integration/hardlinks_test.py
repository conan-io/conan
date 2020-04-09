import os
import platform
import unittest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, TestServer
from conans.client.tools.files import chdir
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID

conanfile = """
import os
from conans import ConanFile

class ExampleConan(ConanFile):
    name = "example"
    version = "0.1.0"
    exports_sources = "*"
    no_copy_source = True

    def package(self):
        self.copy("file_1MB", src=self.source_folder)
        self.copy("file_1MB_link1", src=self.source_folder)
        self.copy("file_1MB_link2", src=self.source_folder)
"""


@unittest.skipUnless(platform.system() != "Windows", "Requires Hardlinks")
class HardLinksTest(unittest.TestCase):

    def test_conan_package_size(self):
        client = TestClient(servers={"default": TestServer(write_permissions=[("*/*@*/*", "*")])},
                            users={"default": [("conan", "password")]})
        client.save({"conanfile.py": conanfile})

        with chdir(client.current_folder):
            filename = "file_1MB"
            with open(filename, "wb") as fd:
                fd.write(os.urandom(1024*1024))
            for i in range(2):
                os.link(filename, filename + "_link" + str(i + 1))

        client.run("create . conan/testing")
        self.assertIn("package(): Packaged 3 files", client.out)

        # Each file must be 1MB
        ref = ConanFileReference("example", "0.1.0", "conan", "testing")
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID, None)
        package_folder = client.cache.package_layout(pref.ref).package(pref)
        for filename in ["file_1MB", "file_1MB_link1", "file_1MB_link2"]:
            size = os.stat(os.path.join(package_folder, filename)).st_size
            self.assertEqual(size, 1048576)

        client.run("upload * --all --confirm")
        self.assertIn("Uploading conan_package.tgz", client.out)
        size = os.stat(os.path.join(package_folder, "conan_package.tgz")).st_size
        self.assertAlmostEqual(size, 3147112, delta=1000)
