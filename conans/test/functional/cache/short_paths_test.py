import os
import platform
import shutil
import textwrap
import unittest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient


@unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
class ShortPathsTest(unittest.TestCase):

    def test_inconsistent_cache(self):
        conanfile = """
import os
from conans import ConanFile, tools


class TestConan(ConanFile):
    name = "test"
    version = "1.0"
    short_paths = {0}
    exports_sources = "source_file.cpp"

    def source(self):
        for item in os.listdir(self.source_folder):
            self.output.info("SOURCE: " + str(item))
    def build(self):
        tools.save(os.path.join(self.build_folder, "artifact"), "")
        for item in os.listdir(self.build_folder):
            self.output.info("BUILD: " + str(item))
    def package(self):
        self.copy("source_file.cpp")
        self.copy("artifact")
        for item in os.listdir(self.build_folder):
            self.output.info("PACKAGE: " + str(item))
"""

        client = TestClient()
        client.save({"conanfile.py": conanfile.format("False"),
                     "source_file.cpp": ""})
        client.run("create . danimtb/testing")
        ref = ConanFileReference("test", "1.0", "danimtb", "testing")
        source_folder = os.path.join(client.cache.package_layout(ref).base_folder(), "source")
        build_folder = os.path.join(client.cache.package_layout(ref).base_folder(), "build",
                                    NO_SETTINGS_PACKAGE_ID)
        package_folder = os.path.join(client.cache.package_layout(ref).base_folder(), "package",
                                      NO_SETTINGS_PACKAGE_ID)
        self.assertIn("SOURCE: source_file.cpp", client.out)
        self.assertEqual(["source_file.cpp"], os.listdir(source_folder))
        self.assertIn("BUILD: source_file.cpp", client.out)
        self.assertIn("BUILD: artifact", client.out)
        self.assertEqual(
            sorted(["artifact", "conanbuildinfo.txt", "conaninfo.txt", "source_file.cpp"]),
            sorted(os.listdir(build_folder)))
        self.assertIn("PACKAGE: source_file.cpp", client.out)
        self.assertIn("PACKAGE: artifact", client.out)
        self.assertEqual(
            sorted(["artifact", "conaninfo.txt", "conanmanifest.txt", "source_file.cpp"]),
            sorted(os.listdir(package_folder)))
        client.save({"conanfile.py": conanfile.format("True")})
        client.run("create . danimtb/testing")
        self.assertIn("SOURCE: source_file.cpp", client.out)
        self.assertEqual([".conan_link"], os.listdir(source_folder))
        self.assertIn("BUILD: source_file.cpp", client.out)
        self.assertIn("BUILD: artifact", client.out)
        self.assertEqual([".conan_link"], os.listdir(build_folder))
        self.assertIn("PACKAGE: source_file.cpp", client.out)
        self.assertIn("PACKAGE: artifact", client.out)
        self.assertEqual([".conan_link"], os.listdir(package_folder))

    def test_package_output(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class TestConan(ConanFile):
                name = "test"
                version = "1.0"
                short_paths = True
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . danimtb/testing")
        self.assertNotIn("test/1.0@danimtb/testing: Package '1' created", client.out)
        self.assertIn("test/1.0@danimtb/testing: Package '%s' created" % NO_SETTINGS_PACKAGE_ID,
                      client.out)

        # try local flow still works, but no pkg id available
        client.run("install .")
        client.run("package .")
        self.assertIn("conanfile.py (test/1.0): Package 'package' created", client.out)

        # try export-pkg with package folder
        client.run("remove test/1.0@danimtb/testing --force")
        client.run("export-pkg . test/1.0@danimtb/testing --package-folder package")
        self.assertIn("test/1.0@danimtb/testing: Package '%s' created" % NO_SETTINGS_PACKAGE_ID,
                      client.out)

        # try export-pkg without package folder
        client.run("remove test/1.0@danimtb/testing --force")
        client.run("export-pkg . test/1.0@danimtb/testing --install-folder .")
        self.assertIn("test/1.0@danimtb/testing: Package '%s' created" % NO_SETTINGS_PACKAGE_ID,
                      client.out)

        # try conan get
        client.run("get test/1.0@danimtb/testing . -p %s" % NO_SETTINGS_PACKAGE_ID)
        self.assertIn("conaninfo.txt", client.out)
        self.assertIn("conanmanifest.txt", client.out)

    def test_package_folder_removed(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class TestConan(ConanFile):
                short_paths = True
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . test/1.0@")
        self.assertIn("test/1.0: Package '%s' created" % NO_SETTINGS_PACKAGE_ID, client.out)
        ref = ConanFileReference.loads("test/1.0")
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID)
        pkg_folder = client.cache.package_layout(ref).package(pref)

        shutil.rmtree(pkg_folder)

        client.run("install test/1.0@", assert_error=True)
        self.assertIn("ERROR: Package 'test/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9' corrupted."
                      " Package folder must exist:", client.out)
        client.run("remove test/1.0@ -p -f")
        client.run("install test/1.0@", assert_error=True)
        self.assertIn("ERROR: Missing binary: test/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.out)
