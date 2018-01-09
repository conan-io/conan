import unittest
import os
from conans.paths import CONANFILE, CONAN_MANIFEST
from conans.util.files import save, load
from conans.model.ref import ConanFileReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.manifest import FileTreeManifest
from conans.test.utils.tools import TestClient
import stat
from nose_parameterized import parameterized


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
        client.run("export . lasote/stable")
        self.assertIn("WARN: Conanfile doesn't have 'license'", client.user_io.out)
        client.run("install Hello/1.2@lasote/stable -s os=Windows", ignore_error=True)
        self.assertIn("'Windows' is not a valid 'settings.os' value", client.user_io.out)
        self.assertIn("Possible values are ['Linux']", client.user_io.out)

    def export_without_full_reference_test(self):
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    pass
"""})
        error = client.run("export . lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("conanfile didn't specify name", client.out)

        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    name="Lib"
"""})
        error = client.run("export . lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("conanfile didn't specify version", client.out)

        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    pass
"""})
        client.run("export . lib/1.0@lasote/channel")
        self.assertIn("lib/1.0@lasote/channel: A new conanfile.py version was exported",
                      client.out)

        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    name="Lib"
    version="1.0"
"""})
        error = client.run("export . lasote", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Invalid parameter 'lasote', specify the full reference or user/channel",
                      client.out)

    def test_export_read_only(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "1.2"
    exports = "file1.txt"
    exports_sources = "file2.txt"
"""
        ref = ConanFileReference.loads("Hello/1.2@lasote/stable")
        export_path = client.client_cache.export(ref)
        export_src_path = client.client_cache.export_sources(ref)

        files = {CONANFILE: conanfile,
                 "file1.txt": "",
                 "file2.txt": ""}
        client.save(files)
        mode1 = os.stat(os.path.join(client.current_folder, "file1.txt")).st_mode
        mode2 = os.stat(os.path.join(client.current_folder, "file2.txt")).st_mode
        os.chmod(os.path.join(client.current_folder, "file1.txt"), mode1 &~ stat.S_IWRITE)
        os.chmod(os.path.join(client.current_folder, "file2.txt"), mode2 &~ stat.S_IWRITE)

        client.run("export . lasote/stable")
        self.assertEqual(load(os.path.join(export_path, "file1.txt")), "")
        self.assertEqual(load(os.path.join(export_src_path, "file2.txt")), "")
        with self.assertRaises(IOError):
            save(os.path.join(export_path, "file1.txt"), "")
        with self.assertRaises(IOError):
            save(os.path.join(export_src_path, "file2.txt"), "")
        self.assertIn("WARN: Conanfile doesn't have 'license'", client.user_io.out)
        files = {CONANFILE: conanfile,
                 "file1.txt": "file1",
                 "file2.txt": "file2"}
        os.chmod(os.path.join(client.current_folder, "file1.txt"), mode1 | stat.S_IWRITE)
        os.chmod(os.path.join(client.current_folder, "file2.txt"), mode2 | stat.S_IWRITE)
        client.save(files)
        client.run("export . lasote/stable")

        self.assertEqual(load(os.path.join(export_path, "file1.txt")), "file1")
        self.assertEqual(load(os.path.join(export_src_path, "file2.txt")), "file2")
        client.run("install Hello/1.2@lasote/stable --build=missing")
        self.assertIn("Hello/1.2@lasote/stable: Generating the package", client.out)

        files = {CONANFILE: conanfile,
                 "file1.txt": "",
                 "file2.txt": ""}
        client.save(files)
        os.chmod(os.path.join(client.current_folder, "file1.txt"), mode1 &~ stat.S_IWRITE)
        os.chmod(os.path.join(client.current_folder, "file2.txt"), mode2 &~ stat.S_IWRITE)
        client.run("export . lasote/stable")
        self.assertEqual(load(os.path.join(export_path, "file1.txt")), "")
        self.assertEqual(load(os.path.join(export_src_path, "file2.txt")), "")
        client.run("install Hello/1.2@lasote/stable --build=Hello")
        self.assertIn("Hello/1.2@lasote/stable: Generating the package", client.out)

    def test_code_parent(self):
        """ when referencing the parent, the relative folder "sibling" will be kept
        """
        base = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "1.2"
    exports = "../*.txt"
"""
        for conanfile in (base, base.replace("../*.txt", "../sibling*")):
            client = TestClient()
            files = {"recipe/conanfile.py": conanfile,
                     "sibling/file.txt": "Hello World!"}
            client.save(files)
            client.current_folder = os.path.join(client.current_folder, "recipe")
            client.run("export . lasote/stable")
            conan_ref = ConanFileReference("Hello", "1.2", "lasote", "stable")
            export_path = client.paths.export(conan_ref)
            content = load(os.path.join(export_path, "sibling/file.txt"))
            self.assertEqual("Hello World!", content)

    def test_code_sibling(self):
        # if provided a path with slash, it will use as a export base
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "1.2"
    exports = "../sibling/*.txt"
"""
        files = {"recipe/conanfile.py": conanfile,
                 "sibling/file.txt": "Hello World!"}
        client.save(files)
        client.current_folder = os.path.join(client.current_folder, "recipe")
        client.run("export . lasote/stable")
        conan_ref = ConanFileReference("Hello", "1.2", "lasote", "stable")
        export_path = client.paths.export(conan_ref)
        content = load(os.path.join(export_path, "file.txt"))
        self.assertEqual("Hello World!", content)

    def test_code_several_sibling(self):
        # if provided a path with slash, it will use as a export base
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "1.2"
    exports_sources = "../test/src/*", "../cpp/*", "../include/*"
"""
        files = {"recipe/conanfile.py": conanfile,
                 "test/src/file.txt": "Hello World!",
                 "cpp/file.cpp": "Hello World!",
                 "include/file.h": "Hello World!"}
        client.save(files)
        client.current_folder = os.path.join(client.current_folder, "recipe")
        client.run("export . lasote/stable")
        conan_ref = ConanFileReference("Hello", "1.2", "lasote", "stable")
        export_path = client.paths.export_sources(conan_ref)
        self.assertEqual(sorted(['file.txt', 'file.cpp', 'file.h']),
                         sorted(os.listdir(export_path)))

    @parameterized.expand([("myconanfile.py", ), ("Conanfile.py", )])
    def test_filename(self, filename):
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "1.2"
"""

        client.save({filename: conanfile})
        client.run("export %s lasote/stable" % filename)
        self.assertIn("Hello/1.2@lasote/stable: A new conanfile.py version was exported",
                      client.user_io.out)
        conan_ref = ConanFileReference("Hello", "1.2", "lasote", "stable")
        export_path = client.paths.export(conan_ref)
        conanfile = load(os.path.join(export_path, "conanfile.py"))
        self.assertIn('name = "Hello"', conanfile)
        manifest = load(os.path.join(export_path, "conanmanifest.txt"))
        self.assertIn('conanfile.py: cac514c81a0af0d87fa379b0bf16fbaa', manifest)

    def test_exclude_basic(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "1.2"
    exports = "*.txt", "!*file1.txt"
    exports_sources = "*.cpp", "!*temp.cpp"
"""

        client.save({CONANFILE: conanfile,
                     "file.txt": "",
                     "file1.txt": "",
                     "file.cpp": "",
                     "file_temp.cpp": ""})
        client.run("export . lasote/stable")
        conan_ref = ConanFileReference("Hello", "1.2", "lasote", "stable")
        export_path = client.paths.export(conan_ref)
        exports_sources_path = client.paths.export_sources(conan_ref)
        self.assertTrue(os.path.exists(os.path.join(export_path, "file.txt")))
        self.assertFalse(os.path.exists(os.path.join(export_path, "file1.txt")))
        self.assertTrue(os.path.exists(os.path.join(exports_sources_path, "file.cpp")))
        self.assertFalse(os.path.exists(os.path.join(exports_sources_path, "file_temp.cpp")))

    def test_exclude_folders(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "1.2"
    exports = "*.txt", "!*/temp/*"
"""

        client.save({CONANFILE: conanfile,
                     "file.txt": "",
                     "any/temp/file1.txt": "",
                     "other/sub/file2.txt": ""})
        client.run("export . lasote/stable")
        conan_ref = ConanFileReference("Hello", "1.2", "lasote", "stable")
        export_path = client.paths.export(conan_ref)
        self.assertTrue(os.path.exists(os.path.join(export_path, "file.txt")))
        self.assertFalse(os.path.exists(os.path.join(export_path, "any/temp/file1.txt")))
        self.assertTrue(os.path.exists(os.path.join(export_path, "other/sub/file2.txt")))


class ExportTest(unittest.TestCase):

    def setUp(self):
        self.conan = TestClient()
        self.files = cpp_hello_conan_files("Hello0", "0.1")
        self.conan_ref = ConanFileReference("Hello0", "0.1", "lasote", "stable")
        self.conan.save(self.files)
        self.conan.run("export . lasote/stable")

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
                         'CMakeLists.txt': '52546396c42f16be3daf72ecf7ab7143',
                         'conanfile.py': '355949fbf0b4fc32b8f1c5a338dfe1ae',
                         'executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'helloHello0.h': '9448df034392fc8781a47dd03ae71bdd'}
        self.assertEqual(expected_sums, manif.file_sums)

    def test_case_sensitive(self):
        self.files = cpp_hello_conan_files("hello0", "0.1")
        self.conan_ref = ConanFileReference("hello0", "0.1", "lasote", "stable")
        self.conan.save(self.files)
        error = self.conan.run("export . lasote/stable", ignore_error=True)
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
        self.conan.run("export . lasote/stable")
        reg_path = self.conan.paths.export(ConanFileReference.loads('openssl/2.0.1@lasote/stable'))
        self.assertEqual(sorted(os.listdir(reg_path)),
                         [CONANFILE, CONAN_MANIFEST])

        content = """
from conans import ConanFile

class OpenSSLConan(ConanFile):
    name = "openssl"
    version = "2.0.1"
    exports = ('*.txt', '*.h')
"""
        save(os.path.join(self.conan.current_folder, CONANFILE), content)
        self.conan.run("export . lasote/stable")
        reg_path = self.conan.paths.export(ConanFileReference.loads('openssl/2.0.1@lasote/stable'))
        self.assertEqual(sorted(os.listdir(reg_path)),
                         ['CMakeLists.txt', CONANFILE, CONAN_MANIFEST,
                          'helloHello0.h'])

        # Now exports being a list instead a tuple
        content = """
from conans import ConanFile

class OpenSSLConan(ConanFile):
    name = "openssl"
    version = "2.0.1"
    exports = ['*.txt', '*.h']
"""
        save(os.path.join(self.conan.current_folder, CONANFILE), content)
        self.conan.run("export . lasote/stable")
        reg_path = self.conan.paths.export(ConanFileReference.loads('openssl/2.0.1@lasote/stable'))
        self.assertEqual(sorted(os.listdir(reg_path)),
                         ['CMakeLists.txt', CONANFILE, CONAN_MANIFEST, 'helloHello0.h'])

    def test_export_the_same_code(self):
        file_list = self._create_packages_and_builds()
        # Export the same conans

        conan2 = TestClient(self.conan.base_folder)
        files2 = cpp_hello_conan_files("Hello0", "0.1")
        conan2.save(files2)
        conan2.run("export . lasote/stable")
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
                         'CMakeLists.txt': '52546396c42f16be3daf72ecf7ab7143',
                         'conanfile.py': '355949fbf0b4fc32b8f1c5a338dfe1ae',
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
        conan2.run("export . lasote/stable")

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
                         'CMakeLists.txt': '52546396c42f16be3daf72ecf7ab7143',
                         'conanfile.py': 'ad17cf00b3142728b03ac37782b9acd9',
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
