import unittest
from conans.test.tools import TestClient
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE, CONANINFO
import os
from conans.model.info import ConanInfo
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import CONANFILE_TXT
import platform
from conans.client.detect import detected_os
from conans.test.utils.test_files import temp_folder
from conans.util.files import load


class InstallTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        self.settings = ("-s os=Windows -s compiler='Visual Studio' -s compiler.version=12 "
                         "-s arch=x86 -s compiler.runtime=MD")

    def _create(self, number, version, deps=None, export=True, no_config=False):
        files = cpp_hello_conan_files(number, version, deps, build=False, config=not no_config)

        self.client.save(files, clean_first=True)
        if export:
            self.client.run("export lasote/stable")

    def imports_test(self):
        """ Ensure that when importing files in a global path, outside the package build,
        they are not deleted
        """
        dst_global_folder = temp_folder().replace("\\", "/")
        conanfile = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"

    def package(self):
        self.copy("*", dst="files")
'''
        conanfile2 = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "Say"
    version = "0.1"
    requires = "Hello/0.1@lasote/stable"

    def imports(self):
        self.copy("*file.txt", dst="%s", src="files")
''' % dst_global_folder

        self.client.save({CONANFILE: conanfile, "other/folder/file.txt": "My file content"})
        self.client.run("export lasote/stable")
        self.client.save({CONANFILE: conanfile2}, clean_first=True)
        self.client.run("export lasote/stable")

        self.client.current_folder = temp_folder()
        self.client.run("install Say/0.1@lasote/stable --build=missing")
        content = load(os.path.join(dst_global_folder, "other/folder/file.txt"))
        self.assertTrue(content, "My file content")

    def reuse_test(self):
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False)

        for lang, id0, id1 in [(0, "2e38bbc2c3ef1425197c8e2ffa8532894c347d26",
                                   "44671ecdd9c606eb7166f2197ab50be8d36a3c3b"),
                               (1, "8b964e421a5b7e48b7bc19b94782672be126be8b",
                                   "3eeab577a3134fa3afdcd82881751789ec48e08f")]:

            self.client.run("install -o language=%d %s --build missing" % (lang, self.settings))
            info_path = os.path.join(self.client.current_folder, CONANINFO)
            conan_info = ConanInfo.load_file(info_path)
            self.assertEqual("arch=x86\n"
                             "compiler=Visual Studio\n"
                             "compiler.runtime=MD\n"
                             "compiler.version=12\n"
                             "os=Windows",
                             conan_info.settings.dumps())
            self.assertEqual("language=%s\nstatic=True" % lang, conan_info.options.dumps())
            conan_ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")

            hello0 = self.client.paths.package(PackageReference(conan_ref, id0))
            hello0_info = os.path.join(hello0, CONANINFO)
            hello0_conan_info = ConanInfo.load_file(hello0_info)
            self.assertEqual(lang, hello0_conan_info.options.language)

            package_ref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"),
                                            id1)
            hello1 = self.client.paths.package(package_ref1)
            hello1_info = os.path.join(hello1, CONANINFO)
            hello1_conan_info = ConanInfo.load_file(hello1_info)
            self.assertEqual(lang, hello1_conan_info.options.language)

    def upper_option_test(self):
        self._create("Hello0", "0.1", no_config=True)
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"], no_config=True)
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False, no_config=True)

        self.client.run("install -o Hello2:language=1 -o Hello1:language=0 -o Hello0:language=1 %s"
                        " --build missing" % self.settings)
        info_path = os.path.join(self.client.current_folder, CONANINFO)
        conan_info = ConanInfo.load_file(info_path)
        self.assertEqual("language=1\nstatic=True", conan_info.options.dumps())
        conan_ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")

        hello0 = self.client.paths.package(PackageReference(conan_ref,
                                           "8b964e421a5b7e48b7bc19b94782672be126be8b"))
        hello0_info = os.path.join(hello0, CONANINFO)
        hello0_conan_info = ConanInfo.load_file(hello0_info)
        self.assertEqual(1, hello0_conan_info.options.language)

        package_ref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"),
                                        "44671ecdd9c606eb7166f2197ab50be8d36a3c3b")
        hello1 = self.client.paths.package(package_ref1)
        hello1_info = os.path.join(hello1, CONANINFO)
        hello1_conan_info = ConanInfo.load_file(hello1_info)
        self.assertEqual(0, hello1_conan_info.options.language)

    def inverse_upper_option_test(self):
        self._create("Hello0", "0.1", no_config=True)
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"], no_config=True)
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False, no_config=True)

        self.client.run("install -o language=0 -o Hello1:language=1 -o Hello0:language=0 %s "
                        "--build missing" % self.settings)
        info_path = os.path.join(self.client.current_folder, CONANINFO)

        conan_info = ConanInfo.load_file(info_path)

        self.assertEqual("language=0\nstatic=True", conan_info.options.dumps())
        conan_ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")

        hello0 = self.client.paths.package(PackageReference(conan_ref,
                                           "2e38bbc2c3ef1425197c8e2ffa8532894c347d26"))
        hello0_info = os.path.join(hello0, CONANINFO)
        hello0_conan_info = ConanInfo.load_file(hello0_info)
        self.assertEqual("language=0\nstatic=True", hello0_conan_info.options.dumps())

        package_ref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"),
                                        "3eeab577a3134fa3afdcd82881751789ec48e08f")
        hello1 = self.client.paths.package(package_ref1)
        hello1_info = os.path.join(hello1, CONANINFO)
        hello1_conan_info = ConanInfo.load_file(hello1_info)
        self.assertEqual("language=1\nstatic=True", hello1_conan_info.options.dumps())

    def upper_option_txt_test(self):
        self._create("Hello0", "0.1", no_config=True)
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"], no_config=True)

        files = cpp_hello_conan_files("Hello2", "0.1", ["Hello1/0.1@lasote/stable"])
        files.pop(CONANFILE)
        files[CONANFILE_TXT] = """[requires]
        Hello1/0.1@lasote/stable

        [options]
        Hello0:language=1
        Hello1:language=0
        """
        self.client.save(files, clean_first=True)

        self.client.run("install %s --build missing" % self.settings)
        info_path = os.path.join(self.client.current_folder, CONANINFO)
        conan_info = ConanInfo.load_file(info_path)
        self.assertEqual("", conan_info.options.dumps())
        conan_ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")

        hello0 = self.client.paths.package(PackageReference(conan_ref,
                                           "8b964e421a5b7e48b7bc19b94782672be126be8b"))
        hello0_info = os.path.join(hello0, CONANINFO)
        hello0_conan_info = ConanInfo.load_file(hello0_info)
        self.assertEqual(1, hello0_conan_info.options.language)

        package_ref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"),
                                        "44671ecdd9c606eb7166f2197ab50be8d36a3c3b")
        hello1 = self.client.paths.package(package_ref1)
        hello1_info = os.path.join(hello1, CONANINFO)
        hello1_conan_info = ConanInfo.load_file(hello1_info)
        self.assertEqual(0, hello1_conan_info.options.language)

    def change_option_txt_test(self):
        self._create("Hello0", "0.1")

        client = TestClient(base_folder=self.client.base_folder)
        files = {CONANFILE_TXT: """[requires]
        Hello0/0.1@lasote/stable

        [options]
        Hello0:language=1
        """}
        client.save(files)

        client.run("install %s --build missing" % self.settings)
        info_path = os.path.join(client.current_folder, CONANINFO)
        conan_info = ConanInfo.load_file(info_path)
        self.assertEqual("", conan_info.options.dumps())
        self.assertIn("Hello0:language=1", conan_info.full_options.dumps())
        self.assertIn("Hello0/0.1@lasote/stable:8b964e421a5b7e48b7bc19b94782672be126be8b",
                      conan_info.full_requires.dumps())

        files = {CONANFILE_TXT: """[requires]
        Hello0/0.1@lasote/stable

        [options]
        Hello0:language=0
        """}
        client.save(files)
        client.run("install %s --build missing" % self.settings)

        info_path = os.path.join(client.current_folder, CONANINFO)
        conan_info = ConanInfo.load_file(info_path)
        self.assertEqual("", conan_info.options.dumps())
        self.assertIn("Hello0:language=0", conan_info.full_options.dumps())
        self.assertIn("Hello0/0.1@lasote/stable:2e38bbc2c3ef1425197c8e2ffa8532894c347d26",
                      conan_info.full_requires.dumps())

    def warn_bad_os_test(self):
        bad_os = "Linux" if platform.system() != "Linux" else "Macos"
        message = "You are building this package with settings.os='%s" % bad_os
        self._create("Hello0", "0.1")
        self.client.run("install Hello0/0.1@lasote/stable -s os=%s" % bad_os, ignore_error=True)
        self.assertIn(message, self.client.user_io.out)

        self.client.run("install Hello0/0.1@lasote/stable -s os=%s" % detected_os(),
                        ignore_error=True)
        self.assertNotIn("You are building this package with settings.os", self.client.user_io.out)
