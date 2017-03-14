import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE, CONANINFO, BUILD_INFO_CMAKE
import os
from conans.model.info import ConanInfo
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import mkdir, load


class InstallSubfolderTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        self.settings = ("-s os=Windows -s compiler='Visual Studio' -s compiler.version=12 "
                         "-s arch=x86 -s compiler.runtime=MD")

    def _create(self, number, version, deps=None, export=True):
        files = cpp_hello_conan_files(number, version, deps, build=False)

        files[CONANFILE] = files[CONANFILE] + """    def build(self):
        self.output.info("Settings %s" % self.settings.values.dumps())
        self.output.info("Options %s" % self.options.values.dumps())
        """
        self.client.save(files, clean_first=True)
        if export:
            self.client.run("export lasote/stable")

    def reuse_test(self):
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False)

        current_folder = self.client.current_folder
        h00 = "2e38bbc2c3ef1425197c8e2ffa8532894c347d26"
        h10 = "44671ecdd9c606eb7166f2197ab50be8d36a3c3b"
        h01 = "8b964e421a5b7e48b7bc19b94782672be126be8b"
        h11 = "3eeab577a3134fa3afdcd82881751789ec48e08f"
        for lang, id0, id1, id2, id3 in [(0, h00, h10, h01, h11),
                                         (1, h01, h11, h00, h10)]:
            self.client.current_folder = os.path.join(current_folder, "lang%dbuild" % lang)
            mkdir(self.client.current_folder)
            self.client.run("install .. -o language=%d %s --build missing" % (lang, self.settings))
            info_path = os.path.join(self.client.current_folder, CONANINFO)
            conan_info = ConanInfo.load_file(info_path)
            self.assertEqual("arch=x86\n"
                             "compiler=Visual Studio\n"
                             "compiler.runtime=MD\n"
                             "compiler.version=12\n"
                             "os=Windows",
                             conan_info.settings.dumps())
            conan_info_text = load(info_path)
            self.assertIn(id0, conan_info_text)
            self.assertIn(id1, conan_info_text)
            self.assertNotIn(id2, conan_info_text)
            self.assertNotIn(id3, conan_info_text)
            self.assertEqual("language=%s\nstatic=True" % lang, conan_info.options.dumps())
            build_cmake = os.path.join(self.client.current_folder, BUILD_INFO_CMAKE)
            build_cmake_text = load(build_cmake)
            self.assertIn(id0, build_cmake_text)
            self.assertIn(id1, build_cmake_text)
            self.assertNotIn(id2, build_cmake_text)
            self.assertNotIn(id3, build_cmake_text)

        # Now test "build" command in subfolders
        for lang, id0, id1, id2, id3 in [(0, h00, h10, h01, h11),
                                         (1, h01, h11, h00, h10)]:
            self.client.current_folder = os.path.join(current_folder, "lang%dbuild" % lang)
            self.client.run("build ..")
            self.assertIn("compiler=Visual Studio", self.client.user_io.out)
            self.assertIn("language=%d" % lang, self.client.user_io.out)
            self.assertNotIn("language=%d" % (not lang), self.client.user_io.out)
