import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import load
import os


conanfile = """from conans import ConanFile

class TestConan(ConanFile):
    name = "%s"
    version = "0.1"
    exports = "*"
    def package(self):
        self.copy("*")
"""


class ImportTest(unittest.TestCase):
    def _set_up(self):
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
        return client

    def imports_folders_test(self):
        client = self._set_up()

        testconanfile = conanfile % "LibD" + "    requires='LibC/0.1@lasote/testing'"
        testconanfile += """
    def imports(self):
        self.copy("license*", dst="licenses", folder=True, ignore_case=True)
        import os
        self.output.info("IMPORTED FOLDERS: %s " % sorted(os.listdir(self.imports_folder)))
"""
        client.save({"conanfile.py": testconanfile}, clean_first=True)
        client.run("install --build=missing")
        self.assertIn("IMPORTED FOLDERS: [", client.user_io.out)
        self.assertEqual(load(os.path.join(client.current_folder, "licenses/LibA/LICENSE.txt")),
                         "LicenseA")
        self.assertEqual(load(os.path.join(client.current_folder, "licenses/LibB/LICENSE.md")),
                         "LicenseB")
        self.assertEqual(load(os.path.join(client.current_folder, "licenses/LibC/license.txt")),
                         "LicenseC")

    def imports_folders_txt_test(self):
        client = self._set_up()

        conanfile = """[requires]
LibC/0.1@lasote/testing
[imports]
., license* -> licenses @ folder=True, ignore_case=True, excludes=*.md # comment
"""
        client.save({"conanfile.txt": conanfile}, clean_first=True)
        client.run("install --build=missing")
        self.assertEqual(load(os.path.join(client.current_folder, "licenses/LibA/LICENSE.txt")),
                         "LicenseA")
        self.assertFalse(os.path.exists(os.path.join(client.current_folder,
                                                     "licenses/LibB/LICENSE.md")))
        self.assertEqual(load(os.path.join(client.current_folder, "licenses/LibC/license.txt")),
                         "LicenseC")
