import unittest
import os
from conans.util.files import load
from conans.model.ref import ConanFileReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.manifest import FileTreeManifest
from conans.test.utils.tools import TestClient
from conans.test.utils.test_files import temp_folder


class ExportPathTest(unittest.TestCase):

    def test_basic(self):
        current_folder = temp_folder()
        source_folder = os.path.join(current_folder, "source")
        client = TestClient(current_folder=current_folder)
        files = cpp_hello_conan_files("Hello0", "0.1")
        conan_ref = ConanFileReference("Hello0", "0.1", "lasote", "stable")
        client.save(files, path=source_folder)
        client.run("export lasote/stable --path=source")
        reg_path = client.paths.export(conan_ref)
        manif = FileTreeManifest.loads(load(client.paths.digestfile_conanfile(conan_ref)))

        self.assertIn('%s: A new conanfile.py version was exported' % str(conan_ref),
                      client.user_io.out)
        self.assertIn('%s: Folder: %s' % (str(conan_ref), reg_path), client.user_io.out)
        self.assertTrue(os.path.exists(reg_path))

        for name in list(files.keys()):
            self.assertTrue(os.path.exists(os.path.join(reg_path, name)))

        expected_sums = {'hello.cpp': '4f005274b2fdb25e6113b69774dac184',
                         'main.cpp': '0479f3c223c9a656a718f3148e044124',
                         'CMakeLists.txt': '52546396c42f16be3daf72ecf7ab7143',
                         'conanfile.py': '355949fbf0b4fc32b8f1c5a338dfe1ae',
                         'executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'helloHello0.h': '9448df034392fc8781a47dd03ae71bdd'}
        self.assertEqual(expected_sums, manif.file_sums)

    def test_rel_path(self):
        base_folder = temp_folder()
        source_folder = os.path.join(base_folder, "source")
        current_folder = os.path.join(base_folder, "current")
        os.makedirs(current_folder)
        client = TestClient(current_folder=current_folder)
        files = cpp_hello_conan_files("Hello0", "0.1")
        conan_ref = ConanFileReference("Hello0", "0.1", "lasote", "stable")
        client.save(files, path=source_folder)
        client.run("export lasote/stable --path=../source")
        reg_path = client.paths.export(conan_ref)
        manif = FileTreeManifest.loads(load(client.paths.digestfile_conanfile(conan_ref)))

        self.assertIn('%s: A new conanfile.py version was exported' % str(conan_ref),
                      client.user_io.out)
        self.assertIn('%s: Folder: %s' % (str(conan_ref), reg_path), client.user_io.out)
        self.assertTrue(os.path.exists(reg_path))

        for name in list(files.keys()):
            self.assertTrue(os.path.exists(os.path.join(reg_path, name)))

        expected_sums = {'hello.cpp': '4f005274b2fdb25e6113b69774dac184',
                         'main.cpp': '0479f3c223c9a656a718f3148e044124',
                         'CMakeLists.txt': '52546396c42f16be3daf72ecf7ab7143',
                         'conanfile.py': '355949fbf0b4fc32b8f1c5a338dfe1ae',
                         'executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'helloHello0.h': '9448df034392fc8781a47dd03ae71bdd'}
        self.assertEqual(expected_sums, manif.file_sums)

    def test_path(self):
        base_folder = temp_folder()
        source_folder = os.path.join(base_folder, "source")
        current_folder = os.path.join(base_folder, "current")
        client = TestClient(current_folder=current_folder)
        files = cpp_hello_conan_files("Hello0", "0.1")
        conan_ref = ConanFileReference("Hello0", "0.1", "lasote", "stable")
        conanfile = files.pop("conanfile.py")
        client.save(files, path=source_folder)
        conanfile = conanfile.replace("exports = '*'", 'exports = "../source*"')

        client.save({"conanfile.py": conanfile})
        client.run("export lasote/stable")
        reg_path = client.paths.export(conan_ref)
        manif = FileTreeManifest.loads(load(client.paths.digestfile_conanfile(conan_ref)))

        self.assertIn('%s: A new conanfile.py version was exported' % str(conan_ref),
                      client.user_io.out)
        self.assertIn('%s: Folder: %s' % (str(conan_ref), reg_path), client.user_io.out)
        self.assertTrue(os.path.exists(reg_path))

        for name in ['conanfile.py', 'conanmanifest.txt', 'source/main.cpp',
                     'source/executable', 'source/hello.cpp', 'source/CMakeLists.txt',
                     'source/helloHello0.h']:
            self.assertTrue(os.path.exists(os.path.join(reg_path, name)))

        expected_sums = {'source/hello.cpp': '4f005274b2fdb25e6113b69774dac184',
                         'source/main.cpp': '0479f3c223c9a656a718f3148e044124',
                         'source/CMakeLists.txt': '52546396c42f16be3daf72ecf7ab7143',
                         'conanfile.py': '3ac566eb5b2e4df4417003f0e606e237',
                         'source/executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'source/helloHello0.h': '9448df034392fc8781a47dd03ae71bdd'}
        self.assertEqual(expected_sums, manif.file_sums)

    def test_combined(self):
        base_folder = temp_folder()
        source_folder = os.path.join(base_folder, "source")
        conanfile_folder = os.path.join(base_folder, "conan")
        current_folder = os.path.join(base_folder, "current")
        os.makedirs(current_folder)

        client = TestClient(current_folder=current_folder)
        files = cpp_hello_conan_files("Hello0", "0.1")
        conan_ref = ConanFileReference("Hello0", "0.1", "lasote", "stable")
        conanfile = files.pop("conanfile.py")
        client.save(files, path=source_folder)
        conanfile = conanfile.replace("exports = '*'", 'exports = "../source*"')

        client.save({"conanfile.py": conanfile}, path=conanfile_folder)
        client.run("export lasote/stable --path=../conan")
        reg_path = client.paths.export(conan_ref)
        manif = FileTreeManifest.loads(load(client.paths.digestfile_conanfile(conan_ref)))

        self.assertIn('%s: A new conanfile.py version was exported' % str(conan_ref),
                      client.user_io.out)
        self.assertIn('%s: Folder: %s' % (str(conan_ref), reg_path), client.user_io.out)
        self.assertTrue(os.path.exists(reg_path))

        for name in ['conanfile.py', 'conanmanifest.txt', 'source/main.cpp',
                     'source/executable', 'source/hello.cpp', 'source/CMakeLists.txt',
                     'source/helloHello0.h']:
            self.assertTrue(os.path.exists(os.path.join(reg_path, name)))

        expected_sums = {'source/hello.cpp': '4f005274b2fdb25e6113b69774dac184',
                         'source/main.cpp': '0479f3c223c9a656a718f3148e044124',
                         'source/CMakeLists.txt': '52546396c42f16be3daf72ecf7ab7143',
                         'conanfile.py': '3ac566eb5b2e4df4417003f0e606e237',
                         'source/executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'source/helloHello0.h': '9448df034392fc8781a47dd03ae71bdd'}
        self.assertEqual(expected_sums, manif.file_sums)
