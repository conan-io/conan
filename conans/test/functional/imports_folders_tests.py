import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import load
import os
from conans.client.importer import IMPORTS_MANIFESTS


class ImportFoldersTest(unittest.TestCase):

    def basic_test(self):
        conanfile = """from conans import ConanFile

class TestConan(ConanFile):
    name = "%s"
    version = "0.1"
    exports = "*"
    def package(self):
        self.copy("*")
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile % "LibA",
                     "LICENSE.txt": "LicenseA"})
        client.run("export lasote/testing")

        client.save({"conanfile.py": conanfile % "LibB" + "    requires='LibA/0.1@lasote/testing'",
                     "LICENSE.md": "LicenseB"}, clean_first=True)
        client.run("export lasote/testing")

        client.save({"conanfile.py": conanfile % "LibC" + "    requires='LibB/0.1@lasote/testing'",
                     "license.txt": "LicenseC"}, clean_first=True)
        client.run("export lasote/testing")

        conanfile = conanfile % "LibD" + "    requires='LibC/0.1@lasote/testing'"
        conanfile += """
    def imports(self):
        self.copy("license*", dst="licenses", folder=True)
        import os
        self.output.info("IMPORTED FOLDERS: %s " % sorted(os.listdir(self.imports_folder)))
"""
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("install --build=missing")
        self.assertIn("IMPORTED FOLDERS: ['conanbuildinfo.txt', 'conanfile.py', "
                      "'conanfile.pyc', 'conaninfo.txt', 'licenses']", client.user_io.out)
        self.assertEqual(load(os.path.join(client.current_folder, "licenses/LibA/LICENSE.txt")),
                         "LicenseA")
        self.assertEqual(load(os.path.join(client.current_folder, "licenses/LibB/LICENSE.md")),
                         "LicenseB")
        self.assertEqual(load(os.path.join(client.current_folder, "licenses/LibC/license.txt")),
                         "LicenseC")
