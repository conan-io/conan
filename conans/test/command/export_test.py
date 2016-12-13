import unittest
import os
from conans.paths import CONANFILE, CONAN_MANIFEST
from conans.util.files import save, load
from conans.model.ref import ConanFileReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.manifest import FileTreeManifest
from conans.test.tools import TestClient


class ExportSettingsTest(unittest.TestCase):

    def test_basic(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "1.2"
    settings = {"os": ["Linux"]}
"""
        files = {CONANFILE: conanfile}
        client.save(files)
        client.run("export lasote/stable")
        self.assertIn("WARN: Conanfile doesn't have 'license'", client.user_io.out)
        client.run("install Hello/1.2@lasote/stable -s os=Windows", ignore_error=True)
        self.assertIn("'Windows' is not a valid 'settings.os' value", client.user_io.out)
        self.assertIn("Possible values are ['Linux']", client.user_io.out)


class ExportTest(unittest.TestCase):

    def setUp(self):
        self.conan = TestClient()
        self.files = cpp_hello_conan_files("Hello0", "0.1")
        self.conan_ref = ConanFileReference("Hello0", "0.1", "lasote", "stable")
        self.conan.save(self.files)
        self.conan.run("export lasote/stable")

    def test_basic(self):
        """ simple registration of a new conans
        """
        reg_path = self.conan.paths.export(self.conan_ref)
        manif = FileTreeManifest.loads(load(self.conan.paths.digestfile_conanfile(self.conan_ref)))

        self.assertIn('%s: A new conanfile.py version was exported' % str(self.conan_ref),
                      self.conan.user_io.out)
        self.assertIn('%s: Folder: %s' % (str(self.conan_ref), reg_path), self.conan.user_io.out)
        self.assertTrue(os.path.exists(reg_path))

        for name in list(self.files.keys()):
            self.assertTrue(os.path.exists(os.path.join(reg_path, name)))

        expected_sums = {'hello.cpp': '4f005274b2fdb25e6113b69774dac184',
                         'main.cpp': '0479f3c223c9a656a718f3148e044124',
                         'CMakeLists.txt': 'bc3405da4bb0b51a3b9f05aca71e58c8',
                         'conanfile.py': '5632cf850a7161388ab24f42b9bdb3fd',
                         'executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'helloHello0.h': '9448df034392fc8781a47dd03ae71bdd'}
        self.assertEqual(expected_sums, manif.file_sums)

    def test_case_sensitive(self):
        self.files = cpp_hello_conan_files("hello0", "0.1")
        self.conan_ref = ConanFileReference("hello0", "0.1", "lasote", "stable")
        self.conan.save(self.files)
        error = self.conan.run("export lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Cannot export package with same name but different case",
                      self.conan.user_io.out)

    def test_export_filter(self):
        content = """
from conans import ConanFile

class OpenSSLConan(ConanFile):
    name = "openssl"
    version = "2.0.1"
"""
        save(os.path.join(self.conan.current_folder, CONANFILE), content)
        self.conan.run("export lasote/stable")
        reg_path = self.conan.paths.export(ConanFileReference.loads('openssl/2.0.1@lasote/stable'))
        self.assertEqual(sorted(os.listdir(reg_path)), [CONANFILE, CONAN_MANIFEST])

        content = """
from conans import ConanFile

class OpenSSLConan(ConanFile):
    name = "openssl"
    version = "2.0.1"
    exports = ('*.txt', '*.h')
"""
        save(os.path.join(self.conan.current_folder, CONANFILE), content)
        self.conan.run("export lasote/stable")
        reg_path = self.conan.paths.export(ConanFileReference.loads('openssl/2.0.1@lasote/stable'))
        self.assertEqual(sorted(os.listdir(reg_path)),
                         ['CMakeLists.txt', CONANFILE, CONAN_MANIFEST, 'helloHello0.h'])

        # Now exports being a list instead a tuple
        content = """
from conans import ConanFile

class OpenSSLConan(ConanFile):
    name = "openssl"
    version = "2.0.1"
    exports = ['*.txt', '*.h']
"""
        save(os.path.join(self.conan.current_folder, CONANFILE), content)
        self.conan.run("export lasote/stable")
        reg_path = self.conan.paths.export(ConanFileReference.loads('openssl/2.0.1@lasote/stable'))
        self.assertEqual(sorted(os.listdir(reg_path)),
                         ['CMakeLists.txt', CONANFILE, CONAN_MANIFEST,
                          'helloHello0.h'])

    def test_export_the_same_code(self):
        file_list = self._create_packages_and_builds()
        # Export the same conans

        conan2 = TestClient(self.conan.base_folder)
        files2 = cpp_hello_conan_files("Hello0", "0.1")
        conan2.save(files2)
        conan2.run("export lasote/stable")
        reg_path2 = conan2.paths.export(self.conan_ref)
        digest2 = FileTreeManifest.loads(load(conan2.paths.digestfile_conanfile(self.conan_ref)))

        self.assertNotIn('A new Conan version was exported', conan2.user_io.out)
        self.assertNotIn('Cleaning the old builds ...', conan2.user_io.out)
        self.assertNotIn('Cleaning the old packs ...', conan2.user_io.out)
        self.assertNotIn('All the previous packs were cleaned', conan2.user_io.out)
        self.assertIn('%s: A new conanfile.py version was exported' % str(self.conan_ref),
                      self.conan.user_io.out)
        self.assertIn('%s: Folder: %s' % (str(self.conan_ref), reg_path2), self.conan.user_io.out)
        self.assertTrue(os.path.exists(reg_path2))

        for name in list(files2.keys()):
            self.assertTrue(os.path.exists(os.path.join(reg_path2, name)))

        expected_sums = {'hello.cpp': '4f005274b2fdb25e6113b69774dac184',
                         'main.cpp': '0479f3c223c9a656a718f3148e044124',
                         'CMakeLists.txt': 'bc3405da4bb0b51a3b9f05aca71e58c8',
                         'conanfile.py': '5632cf850a7161388ab24f42b9bdb3fd',
                         'executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'helloHello0.h': '9448df034392fc8781a47dd03ae71bdd'}
        self.assertEqual(expected_sums, digest2.file_sums)

        for f in file_list:
            self.assertTrue(os.path.exists(f))

    def test_export_a_new_version(self):
        self._create_packages_and_builds()
        # Export an update of the same conans

        conan2 = TestClient(self.conan.base_folder)
        files2 = cpp_hello_conan_files("Hello0", "0.1")
        files2[CONANFILE] = "# insert comment\n %s" % files2[CONANFILE]
        conan2.save(files2)
        conan2.run("export lasote/stable")

        reg_path3 = conan2.paths.export(self.conan_ref)
        digest3 = FileTreeManifest.loads(load(conan2.paths.digestfile_conanfile(self.conan_ref)))

        self.assertIn('%s: A new conanfile.py version was exported' % str(self.conan_ref),
                      self.conan.user_io.out)
        self.assertIn('%s: Folder: %s' % (str(self.conan_ref), reg_path3), self.conan.user_io.out)

        self.assertTrue(os.path.exists(reg_path3))

        for name in list(files2.keys()):
            self.assertTrue(os.path.exists(os.path.join(reg_path3, name)))

        expected_sums = {'hello.cpp': '4f005274b2fdb25e6113b69774dac184',
                         'main.cpp': '0479f3c223c9a656a718f3148e044124',
                         'CMakeLists.txt': 'bc3405da4bb0b51a3b9f05aca71e58c8',
                         'conanfile.py': '7f7a5352e781be814b86e8f333593b4f',
                         'executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'helloHello0.h': '9448df034392fc8781a47dd03ae71bdd'}
        self.assertEqual(expected_sums, digest3.file_sums)

        # for f in file_list:
        #    self.assertFalse(os.path.exists(f))

    def _create_packages_and_builds(self):
        reg_builds = self.conan.paths.builds(self.conan_ref)
        reg_packs = self.conan.paths.packages(self.conan_ref)

        folders = [os.path.join(reg_builds, '342525g4f52f35f'),
                   os.path.join(reg_builds, 'ew9o8asdf908asdf80'),
                   os.path.join(reg_packs, '342525g4f52f35f'),
                   os.path.join(reg_packs, 'ew9o8asdf908asdf80')]

        file_list = []
        for f in folders:
            for name, content in {'file1.h': 'asddfasdf', 'file1.dll': 'asddfasdf'}.items():
                file_path = os.path.join(f, name)
                save(file_path, content)
                file_list.append(file_path)
        return file_list
