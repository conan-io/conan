import os
import platform
import shutil
import textwrap
import unittest

import pytest
from parameterized import parameterized

from conans.client.tools import environment_append
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
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

    @parameterized.expand([(True,), (False,)])
    def test_leaking_folders(self, use_always_short_paths):
        # https://github.com/conan-io/conan/issues/7983
        client = TestClient(cache_autopopulate=False)
        short_folder = temp_folder()
        # Testing in CI requires setting it via env-var
        with environment_append({"CONAN_USER_HOME_SHORT": short_folder}):
            conanfile = GenConanfile().with_exports_sources("*")
            if use_always_short_paths:
                client.run("config set general.use_always_short_paths=True")
            else:
                conanfile.with_short_paths(True)
            client.save({"conanfile.py": conanfile,
                         "file.h": ""})
            client.run("create . dep/1.0@")
            self.assertEqual(5, len(os.listdir(short_folder)))
            client.run("remove * -f")
            self.assertEqual(0, len(os.listdir(short_folder)))
            client.run("create . dep/1.0@")
            self.assertEqual(5, len(os.listdir(short_folder)))
            client.run("install dep/1.0@")
            self.assertEqual(5, len(os.listdir(short_folder)))
            client.run("install dep/1.0@ --build")
            self.assertEqual(5, len(os.listdir(short_folder)))

    def test_info_paths(self):
        # https://github.com/conan-io/conan/issues/8172
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_short_paths(True)})
        client.run("export . test/1.0@")
        client.run("info test/1.0@ --paths")
        client.run("info test/1.0@ --paths")
