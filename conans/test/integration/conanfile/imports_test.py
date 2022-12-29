import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient

conanfile = """from conans import ConanFile

class TestConan(ConanFile):
    name = "%s"
    version = "0.1"
    exports = "*"
    def package(self):
        self.copy("*")
"""

conanfile_txt = """
[requires]
%s
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

    def test_repackage(self):
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
        self.assertIn("Pkg/0.1@user/testing package(): Packaged 1 '.md' file: LICENSE.md",
                      client.out)
        pref = PackageReference(ConanFileReference.loads("Pkg/0.1@user/testing"),
                                "e6f2dac07251ad9958120a7f7c324366fb3b6f2a")
        pkg_folder = client.cache.package_layout(pref.ref).package(pref)
        self.assertTrue(os.path.exists(os.path.join(pkg_folder, "licenses/LibA/LICENSE.txt")))
        self.assertTrue(os.path.exists(os.path.join(pkg_folder, "licenses/LibB/LICENSE.md")))
        self.assertTrue(os.path.exists(os.path.join(pkg_folder, "licenses/LibC/license.txt")))

    def test_imports_folders(self):
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
        self.assertIn("IMPORTED FOLDERS: [", client.out)
        self.assertEqual(client.load("licenses/LibA/LICENSE.txt"), "LicenseA")
        self.assertEqual(client.load("licenses/LibB/LICENSE.md"), "LicenseB")
        self.assertEqual(client.load("licenses/LibC/license.txt"), "LicenseC")

    def test_imports_folders_txt(self):
        client = self._set_up()

        conanfile = """[requires]
LibC/0.1@lasote/testing
[imports]
., license* -> licenses @ folder=True, ignore_case=True, excludes=*.md # comment
"""
        client.save({"conanfile.txt": conanfile}, clean_first=True)
        client.run("install . --build=missing")
        self.assertEqual(client.load("licenses/LibA/LICENSE.txt"), "LicenseA")
        self.assertFalse(os.path.exists(os.path.join(client.current_folder,
                                                     "licenses/LibB/LICENSE.md")))
        self.assertEqual(client.load("licenses/LibC/license.txt"), "LicenseC")

    def test_imports_wrong_args_txt(self):
        client = TestClient()
        conanfile = """
[imports]
., license* -> lic@myfolder @ something
"""
        client.save({"conanfile.txt": conanfile})
        client.run("install .", assert_error=True)
        self.assertIn("Wrong imports argument 'something'. Need a 'arg=value' pair.", client.out)

    def test_imports_wrong_line_txt(self):
        client = TestClient()
        conanfile = """
[imports]
., license*
"""
        client.save({"conanfile.txt": conanfile})
        client.run("install .", assert_error=True)
        self.assertIn("Wrong imports line: ., license*", client.out)
        self.assertIn("Use syntax: path, pattern -> local-folder", client.out)

    def test_imports_folders_extrachars_txt(self):
        # https://github.com/conan-io/conan/issues/4524
        client = self._set_up()

        conanfile = """[requires]
LibC/0.1@lasote/testing
[imports]
., license* -> lic@myfolder @ folder=True, ignore_case=True, excludes=*.md # comment
., *.md -> lic@myfolder @ # This is mandatory, otherwise it will fail
"""
        client.save({"conanfile.txt": conanfile}, clean_first=True)
        client.run("install . --build=missing")
        self.assertEqual(client.load("lic@myfolder/LibA/LICENSE.txt"), "LicenseA")
        self.assertEqual(client.load("lic@myfolder/LICENSE.md"), "LicenseB")
        self.assertEqual(client.load("lic@myfolder/LibC/license.txt"), "LicenseC")

    def test_conanfile_txt_multi_excludes(self):
        # https://github.com/conan-io/conan/issues/2293
        client = TestClient()
        pkg_conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                exports_sources = "*"
                def package(self):
                    self.copy("*.dll", dst="bin")
            """)
        client.save({"conanfile.py": pkg_conanfile,
                     "a.dll": "",
                     "Foo/b.dll": "",
                     "Baz/b.dll": ""})
        client.run("create . Pkg/0.1@user/testing")

        consumer = textwrap.dedent("""
            [requires]
            Pkg/0.1@user/testing
            [imports]
            bin, *.dll ->  @ excludes=Foo/*.dll Baz/*.dll
            """)
        client.save({"conanfile.txt": consumer}, clean_first=True)
        client.run("install . --build=missing")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "a.dll")))
        self.assertFalse(os.path.exists(os.path.join(client.current_folder, "Foo/b.dll")))
        self.assertFalse(os.path.exists(os.path.join(client.current_folder, "Baz/b.dll")))

    def test_imports_keep_path(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile % "LibC",
                     "path/to/license.txt": "LicenseC"}, clean_first=True)
        client.run("export . lasote/testing")

        # keep_path = True AND conanfile.py
        testconanfile = conanfile % "LibD" + "    requires='LibC/0.1@lasote/testing'"
        testconanfile += """
    def imports(self):
        self.copy("*license*", dst="licenses", keep_path=True)
"""
        client.save({"conanfile.py": testconanfile}, clean_first=True)
        client.run("install . --build=missing")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder,
                                                    "licenses/path/to/license.txt")))

        # keep_path = False AND conanfile.py
        testconanfile = testconanfile.replace("keep_path=True", "keep_path=False")
        client.save({"conanfile.py": testconanfile}, clean_first=True)
        client.run("install . --build=missing")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder,
                                                    "licenses/license.txt")))

        # keep_path = True AND conanfile.txt
        testconanfile = conanfile_txt % "LibC/0.1@lasote/testing"
        testconanfile += """
[imports]:
., *license* -> ./licenses @ keep_path=True
"""
        client.save({"conanfile.txt": testconanfile}, clean_first=True)
        client.run("install . --build=missing")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder,
                                                    "licenses/path/to/license.txt")))

        # keep_path = False AND conanfile.txt
        testconanfile = testconanfile.replace("keep_path=True", "keep_path=False")
        client.save({"conanfile.txt": testconanfile}, clean_first=True)
        client.run("install . --build=missing")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "licenses")))
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "licenses/license.txt")))

    def test_wrong_path_sep(self):
        # https://github.com/conan-io/conan/issues/7856
        pkg_conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import save
            import os

            class TestConan(ConanFile):
                def package(self):
                    save(os.path.join(self.package_folder, "licenses/LICENSE"), "mylicense in file")
                    save(os.path.join(self.package_folder, "licenses/README"), "myreadme in file")
            """)
        client = TestClient()
        client.save({"conanfile.py": pkg_conanfile})
        client.run("create . pkg/0.1@")
        consumer_conanfile = textwrap.dedent(r"""
            from conans import ConanFile
            import platform

            class TestConan(ConanFile):
                requires = "pkg/0.1"

                def imports(self):
                    if platform.system() == "Windows":
                        self.copy("licenses\\LICENSE", dst="deps_licenses", root_package="pkg")
                    else:
                        self.copy("licenses/LICENSE", dst="deps_licenses", root_package="pkg")
                    self.copy("licenses/README", dst="deps_licenses", root_package="pkg")
            """)
        client.save({"conanfile.py": consumer_conanfile})
        client.run("install .")
        pkg_license = client.load("deps_licenses/licenses/LICENSE")
        self.assertEqual(pkg_license, "mylicense in file")
        readme_license = client.load("deps_licenses/licenses/README")
        self.assertEqual(readme_license, "myreadme in file")
