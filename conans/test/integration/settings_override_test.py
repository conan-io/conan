import unittest
from conans.test.utils.tools import TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import CONANFILE, CONANINFO
from conans.model.ref import ConanFileReference
from conans.util.files import load
import os
from conans import tools


class SettingsOverrideTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        files = cpp_hello_conan_files(name="MinGWBuild", version="0.1", build=False)
        self._patch_build_to_print_compiler(files)

        self.client.save(files)
        self.client.run("export . lasote/testing")

    def test_override(self):

        files = cpp_hello_conan_files(name="VisualBuild",
                                      version="0.1", build=False, deps=["MinGWBuild/0.1@lasote/testing"])
        self._patch_build_to_print_compiler(files)
        self.client.save(files)
        self.client.run("export . lasote/testing")
        self.client.run("install VisualBuild/0.1@lasote/testing --build missing -s compiler='Visual Studio' "
                        "-s compiler.version=14 -s compiler.runtime=MD "
                        "-s MinGWBuild:compiler='gcc' -s MinGWBuild:compiler.libcxx='libstdc++' "
                        "-s MinGWBuild:compiler.version=4.8")

        self.assertIn("COMPILER=> MinGWBuild gcc", self.client.user_io.out)
        self.assertIn("COMPILER=> VisualBuild Visual Studio", self.client.user_io.out)

        # CHECK CONANINFO FILE
        packs_dir = self.client.paths.packages(ConanFileReference.loads("MinGWBuild/0.1@lasote/testing"))
        pack_dir = os.path.join(packs_dir, os.listdir(packs_dir)[0])
        conaninfo = load(os.path.join(pack_dir, CONANINFO))
        self.assertIn("compiler=gcc", conaninfo)

        # CHECK CONANINFO FILE
        packs_dir = self.client.paths.packages(ConanFileReference.loads("VisualBuild/0.1@lasote/testing"))
        pack_dir = os.path.join(packs_dir, os.listdir(packs_dir)[0])
        conaninfo = load(os.path.join(pack_dir, CONANINFO))
        self.assertIn("compiler=Visual Studio", conaninfo)
        self.assertIn("compiler.version=14", conaninfo)

    def test_non_existing_setting(self):
        files = cpp_hello_conan_files(name="VisualBuild",
                                      version="0.1", build=False, deps=["MinGWBuild/0.1@lasote/testing"])
        self.client.save(files)
        self.client.run("export . lasote/testing")
        self.client.run("install VisualBuild/0.1@lasote/testing --build missing -s compiler='Visual Studio' "
                        "-s compiler.version=14 -s compiler.runtime=MD "
                        "-s MinGWBuild:missingsetting='gcc' ", ignore_error=True)
        self.assertIn("settings.missingsetting' doesn't exist", self.client.user_io.out)

    def test_override_in_non_existing_recipe(self):
        files = cpp_hello_conan_files(name="VisualBuild",
                                      version="0.1", build=False, deps=["MinGWBuild/0.1@lasote/testing"])
        self._patch_build_to_print_compiler(files)
        self.client.save(files)
        self.client.run("export . lasote/testing")
        self.client.run("install VisualBuild/0.1@lasote/testing --build missing -s compiler='Visual Studio' "
                        "-s compiler.version=14 -s compiler.runtime=MD "
                        "-s MISSINGID:compiler='gcc' ")

        self.assertIn("COMPILER=> MinGWBuild Visual Studio", self.client.user_io.out)
        self.assertIn("COMPILER=> VisualBuild Visual Studio", self.client.user_io.out)

    def test_override_setting_with_env_variables(self):
        files = cpp_hello_conan_files(name="VisualBuild",
                                      version="0.1", build=False, deps=["MinGWBuild/0.1@lasote/testing"])
        self._patch_build_to_print_compiler(files)
        self.client.save(files)
        self.client.run("export . lasote/testing")
        with tools.environment_append({"CONAN_ENV_COMPILER": "Visual Studio",
                                       "CONAN_ENV_COMPILER_VERSION": "14",
                                       "CONAN_ENV_COMPILER_RUNTIME": "MD"}):
            self.client.run("install VisualBuild/0.1@lasote/testing --build missing")

        self.assertIn("COMPILER=> MinGWBuild Visual Studio", self.client.user_io.out)

    def _patch_build_to_print_compiler(self, files):
        files[CONANFILE] = files[CONANFILE] + '''
    def build(self):
        self.output.warn("COMPILER=> %s %s" % (self.name, str(self.settings.compiler)))

'''
