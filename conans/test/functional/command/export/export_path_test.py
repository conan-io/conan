import os
import unittest

from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


class ExportPathTest(unittest.TestCase):

    def test_basic(self):
        current_folder = temp_folder()
        source_folder = os.path.join(current_folder, "source")
        client = TestClient(current_folder=current_folder)
        files = cpp_hello_conan_files("Hello0", "0.1")
        ref = ConanFileReference("Hello0", "0.1", "lasote", "stable")
        client.save(files, path=source_folder)
        client.run("export source lasote/stable")
        reg_path = client.cache.package_layout(ref).export()
        manif = FileTreeManifest.load(client.cache.package_layout(ref).export())

        self.assertIn('%s: A new conanfile.py version was exported' % str(ref),
                      client.out)
        self.assertIn('%s: Folder: %s' % (str(ref), reg_path), client.out)
        self.assertTrue(os.path.exists(reg_path))

        for name in list(files.keys()):
            self.assertTrue(os.path.exists(os.path.join(reg_path, name)))

        expected_sums = {'hello.cpp': '4f005274b2fdb25e6113b69774dac184',
                         'main.cpp': '0479f3c223c9a656a718f3148e044124',
                         'CMakeLists.txt': '10d907c160c360b28f6991397a5aa9b4',
                         'conanfile.py': '1ad1f4b995ae7ffdb00d53ff49e1366f',
                         'executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'helloHello0.h': 'd0a6868b5df17a6ae6e61ebddb0c9eb3'}
        self.assertEqual(expected_sums, manif.file_sums)

    def test_rel_path(self):
        base_folder = temp_folder()
        source_folder = os.path.join(base_folder, "source")
        current_folder = os.path.join(base_folder, "current")
        os.makedirs(current_folder)
        client = TestClient(current_folder=current_folder)
        files = cpp_hello_conan_files("Hello0", "0.1")
        ref = ConanFileReference("Hello0", "0.1", "lasote", "stable")
        client.save(files, path=source_folder)
        client.run("export ../source lasote/stable")
        reg_path = client.cache.package_layout(ref).export()
        manif = FileTreeManifest.load(client.cache.package_layout(ref).export())

        self.assertIn('%s: A new conanfile.py version was exported' % str(ref), client.out)
        self.assertIn('%s: Folder: %s' % (str(ref), reg_path), client.out)
        self.assertTrue(os.path.exists(reg_path))

        for name in list(files.keys()):
            self.assertTrue(os.path.exists(os.path.join(reg_path, name)))

        expected_sums = {'hello.cpp': '4f005274b2fdb25e6113b69774dac184',
                         'main.cpp': '0479f3c223c9a656a718f3148e044124',
                         'CMakeLists.txt': '10d907c160c360b28f6991397a5aa9b4',
                         'conanfile.py': '1ad1f4b995ae7ffdb00d53ff49e1366f',
                         'executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'helloHello0.h': 'd0a6868b5df17a6ae6e61ebddb0c9eb3'}
        self.assertEqual(expected_sums, manif.file_sums)

    def test_path(self):
        base_folder = temp_folder()
        source_folder = os.path.join(base_folder, "source")
        current_folder = os.path.join(base_folder, "current")
        client = TestClient(current_folder=current_folder)
        files = cpp_hello_conan_files("Hello0", "0.1")
        ref = ConanFileReference("Hello0", "0.1", "lasote", "stable")
        conanfile = files.pop("conanfile.py")
        client.save(files, path=source_folder)
        conanfile = conanfile.replace("exports = '*'", 'exports = "../source*"')

        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/stable")
        reg_path = client.cache.package_layout(ref).export()
        manif = FileTreeManifest.load(client.cache.package_layout(ref).export())

        self.assertIn('%s: A new conanfile.py version was exported' % str(ref), client.out)
        self.assertIn('%s: Folder: %s' % (str(ref), reg_path), client.out)
        self.assertTrue(os.path.exists(reg_path))

        for name in ['conanfile.py', 'conanmanifest.txt', 'source/main.cpp',
                     'source/executable', 'source/hello.cpp', 'source/CMakeLists.txt',
                     'source/helloHello0.h']:
            self.assertTrue(os.path.exists(os.path.join(reg_path, name)))

        expected_sums = {'source/hello.cpp': '4f005274b2fdb25e6113b69774dac184',
                         'source/main.cpp': '0479f3c223c9a656a718f3148e044124',
                         'source/CMakeLists.txt': '10d907c160c360b28f6991397a5aa9b4',
                         'conanfile.py': '073cdeb3d07fc62180ba510ad7b4794d',
                         'source/executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'source/helloHello0.h': 'd0a6868b5df17a6ae6e61ebddb0c9eb3'}
        self.assertEqual(expected_sums, manif.file_sums)

    def test_combined(self):
        base_folder = temp_folder()
        source_folder = os.path.join(base_folder, "source")
        conanfile_folder = os.path.join(base_folder, "conan")
        current_folder = os.path.join(base_folder, "current")
        os.makedirs(current_folder)

        client = TestClient(current_folder=current_folder)
        files = cpp_hello_conan_files("Hello0", "0.1")
        ref = ConanFileReference("Hello0", "0.1", "lasote", "stable")
        conanfile = files.pop("conanfile.py")
        client.save(files, path=source_folder)
        conanfile = conanfile.replace("exports = '*'", 'exports = "../source*"')

        client.save({"conanfile.py": conanfile}, path=conanfile_folder)
        client.run("export ../conan lasote/stable")
        reg_path = client.cache.package_layout(ref).export()
        manif = FileTreeManifest.load(client.cache.package_layout(ref).export())

        self.assertIn('%s: A new conanfile.py version was exported' % str(ref), client.out)
        self.assertIn('%s: Folder: %s' % (str(ref), reg_path), client.out)
        self.assertTrue(os.path.exists(reg_path))

        for name in ['conanfile.py', 'conanmanifest.txt', 'source/main.cpp',
                     'source/executable', 'source/hello.cpp', 'source/CMakeLists.txt',
                     'source/helloHello0.h']:
            self.assertTrue(os.path.exists(os.path.join(reg_path, name)))

        expected_sums = {'source/hello.cpp': '4f005274b2fdb25e6113b69774dac184',
                         'source/main.cpp': '0479f3c223c9a656a718f3148e044124',
                         'source/CMakeLists.txt': '10d907c160c360b28f6991397a5aa9b4',
                         'conanfile.py': '073cdeb3d07fc62180ba510ad7b4794d',
                         'source/executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'source/helloHello0.h': 'd0a6868b5df17a6ae6e61ebddb0c9eb3'}
        self.assertEqual(expected_sums, manif.file_sums)
