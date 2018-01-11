import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import load
import os
from conans.model.ref import ConanFileReference, PackageReference


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
        client.run("export . lasote/testing")

        client.save({"conanfile.py": conanfile % "LibB" + "    requires='LibA/0.1@lasote/testing'",
                     "LICENSE.md": "LicenseB"}, clean_first=True)
        client.run("export . lasote/testing")

        client.save({"conanfile.py": conanfile % "LibC" + "    requires='LibB/0.1@lasote/testing'",
                     "license.txt": "LicenseC"}, clean_first=True)
        client.run("export . lasote/testing")
        return client

    def repackage_test(self):
        client = self._set_up()
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):
    requires='LibC/0.1@lasote/testing'
    keep_imports = True
    def imports(self):
        self.copy("license*", dst="licenses", folder=True, ignore_case=True)

    def package(self):
        self.copy("*")
"""
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("create . Pkg/0.1@user/testing --build=missing")
        self.assertIn("Pkg/0.1@user/testing package(): Copied 1 '.md' files: LICENSE.md",
                      client.out)
        pkg_ref = PackageReference(ConanFileReference.loads("Pkg/0.1@user/testing"),
                                   "e6f2dac07251ad9958120a7f7c324366fb3b6f2a")
        pkg_folder = client.client_cache.package(pkg_ref)
        self.assertTrue(os.path.exists(os.path.join(pkg_folder, "licenses/LibA/LICENSE.txt")))
        self.assertTrue(os.path.exists(os.path.join(pkg_folder, "licenses/LibB/LICENSE.md")))
        self.assertTrue(os.path.exists(os.path.join(pkg_folder, "licenses/LibC/license.txt")))

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
        client.run("install . --build=missing")
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
        client.run("install . --build=missing")
        self.assertEqual(load(os.path.join(client.current_folder, "licenses/LibA/LICENSE.txt")),
                         "LicenseA")
        self.assertFalse(os.path.exists(os.path.join(client.current_folder,
                                                     "licenses/LibB/LICENSE.md")))
        self.assertEqual(load(os.path.join(client.current_folder, "licenses/LibC/license.txt")),
                         "LicenseC")

    def conanfile_txt_multi_excludes_test(self):
        # https://github.com/conan-io/conan/issues/2293
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    exports_sources = "*"
    def package(self):
        self.copy("*.dll", dst="bin")
"""
        client.save({"conanfile.py": conanfile,
                     "a.dll": "",
                     "Foo/b.dll": "",
                     "Baz/b.dll": ""})
        client.run("create . Pkg/0.1@user/testing")

        conanfile = """[requires]
Pkg/0.1@user/testing
[imports]
bin, *.dll ->  @ excludes=Foo/*.dll Baz/*.dll
"""
        client.save({"conanfile.txt": conanfile}, clean_first=True)
        client.run("install . --build=missing")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "a.dll")))
        self.assertFalse(os.path.exists(os.path.join(client.current_folder, "Foo/b.dll")))
        self.assertFalse(os.path.exists(os.path.join(client.current_folder, "Baz/b.dll")))
