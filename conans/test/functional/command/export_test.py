import os
import stat
import textwrap
import unittest

from parameterized import parameterized

from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE, CONAN_MANIFEST
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient
from conans.test.utils.tools import create_local_git_repo
from conans.util.files import load, save


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
        self.assertIn("WARN: Conanfile doesn't have 'license'", client.out)
        client.run("install Hello/1.2@lasote/stable -s os=Windows", assert_error=True)
        self.assertIn("'Windows' is not a valid 'settings.os' value", client.out)
        self.assertIn("Possible values are ['Linux']", client.out)

    def export_without_full_reference_test(self):
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    pass
"""})
        client.run("export . lasote/stable", assert_error=True)
        self.assertIn("conanfile didn't specify name", client.out)

        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    name="Lib"
"""})
        client.run("export . lasote/stable", assert_error=True)
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
        client.run("export . lasote", assert_error=True)
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
        export_path = client.cache.package_layout(ref).export()
        export_src_path = client.cache.package_layout(ref).export_sources()

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
        self.assertIn("WARN: Conanfile doesn't have 'license'", client.out)
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
            ref = ConanFileReference("Hello", "1.2", "lasote", "stable")
            export_path = client.cache.package_layout(ref).export()
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
        ref = ConanFileReference("Hello", "1.2", "lasote", "stable")
        export_path = client.cache.package_layout(ref).export()
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
        ref = ConanFileReference("Hello", "1.2", "lasote", "stable")
        export_path = client.cache.package_layout(ref).export_sources()
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
                      client.out)
        ref = ConanFileReference("Hello", "1.2", "lasote", "stable")
        export_path = client.cache.package_layout(ref).export()
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
        ref = ConanFileReference("Hello", "1.2", "lasote", "stable")
        export_path = client.cache.package_layout(ref).export()
        exports_sources_path = client.cache.package_layout(ref).export_sources()
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
        ref = ConanFileReference("Hello", "1.2", "lasote", "stable")
        export_path = client.cache.package_layout(ref).export()
        self.assertTrue(os.path.exists(os.path.join(export_path, "file.txt")))
        self.assertFalse(os.path.exists(os.path.join(export_path, "any/temp/file1.txt")))
        self.assertTrue(os.path.exists(os.path.join(export_path, "other/sub/file2.txt")))


class ExportTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        self.files = cpp_hello_conan_files("Hello0", "0.1")
        self.ref = ConanFileReference("Hello0", "0.1", "lasote", "stable")
        self.client.save(self.files)
        self.client.run("export . lasote/stable")

    def test_basic(self):
        """ simple registration of a new conans
        """
        reg_path = self.client.cache.package_layout(self.ref).export()
        manif = FileTreeManifest.load(self.client.cache.package_layout(self.ref).export())

        self.assertIn('%s: A new conanfile.py version was exported' % str(self.ref),
                      self.client.out)
        self.assertIn('%s: Folder: %s' % (str(self.ref), reg_path), self.client.out)
        self.assertTrue(os.path.exists(reg_path))

        for name in list(self.files.keys()):
            self.assertTrue(os.path.exists(os.path.join(reg_path, name)))

        expected_sums = {'hello.cpp': '4f005274b2fdb25e6113b69774dac184',
                         'main.cpp': '0479f3c223c9a656a718f3148e044124',
                         'CMakeLists.txt': '10d907c160c360b28f6991397a5aa9b4',
                         'conanfile.py': '355949fbf0b4fc32b8f1c5a338dfe1ae',
                         'executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'helloHello0.h': '9448df034392fc8781a47dd03ae71bdd'}
        self.assertEqual(expected_sums, manif.file_sums)

    def test_case_sensitive(self):
        self.files = cpp_hello_conan_files("hello0", "0.1")
        self.ref = ConanFileReference("hello0", "0.1", "lasote", "stable")
        self.client.save(self.files)
        self.client.run("export . lasote/stable", assert_error=True)
        self.assertIn("ERROR: Cannot export package with same name but different case",
                      self.client.out)

    def test_export_filter(self):
        content = """
from conans import ConanFile

class OpenSSLConan(ConanFile):
    name = "openssl"
    version = "2.0.1"
"""
        save(os.path.join(self.client.current_folder, CONANFILE), content)
        self.client.run("export . lasote/stable")
        ref = ConanFileReference.loads('openssl/2.0.1@lasote/stable')
        reg_path = self.client.cache.package_layout(ref).export()
        self.assertEqual(sorted(os.listdir(reg_path)),
                         [CONANFILE, CONAN_MANIFEST])

        content = """
from conans import ConanFile

class OpenSSLConan(ConanFile):
    name = "openssl"
    version = "2.0.1"
    exports = ('*.txt', '*.h')
"""
        save(os.path.join(self.client.current_folder, CONANFILE), content)
        self.client.run("export . lasote/stable")
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
        save(os.path.join(self.client.current_folder, CONANFILE), content)
        self.client.run("export . lasote/stable")
        self.assertEqual(sorted(os.listdir(reg_path)),
                         ['CMakeLists.txt', CONANFILE, CONAN_MANIFEST, 'helloHello0.h'])

    def test_export_the_same_code(self):
        file_list = self._create_packages_and_builds()
        # Export the same conans
        # Do not adjust cpu_count, it is reusing a cache
        client2 = TestClient(self.client.cache_folder, cpu_count=False)
        files2 = cpp_hello_conan_files("Hello0", "0.1")
        client2.save(files2)
        client2.run("export . lasote/stable")
        reg_path2 = client2.cache.package_layout(self.ref).export()
        digest2 = FileTreeManifest.load(client2.cache.package_layout(self.ref).export())

        self.assertNotIn('A new Conan version was exported', client2.out)
        self.assertNotIn('Cleaning the old builds ...', client2.out)
        self.assertNotIn('Cleaning the old packs ...', client2.out)
        self.assertNotIn('All the previous packs were cleaned', client2.out)
        self.assertIn('%s: A new conanfile.py version was exported' % str(self.ref),
                      self.client.out)
        self.assertIn('%s: Folder: %s' % (str(self.ref), reg_path2), self.client.out)
        self.assertTrue(os.path.exists(reg_path2))

        for name in list(files2.keys()):
            self.assertTrue(os.path.exists(os.path.join(reg_path2, name)))

        expected_sums = {'hello.cpp': '4f005274b2fdb25e6113b69774dac184',
                         'main.cpp': '0479f3c223c9a656a718f3148e044124',
                         'CMakeLists.txt': '10d907c160c360b28f6991397a5aa9b4',
                         'conanfile.py': '355949fbf0b4fc32b8f1c5a338dfe1ae',
                         'executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'helloHello0.h': '9448df034392fc8781a47dd03ae71bdd'}
        self.assertEqual(expected_sums, digest2.file_sums)

        for f in file_list:
            self.assertTrue(os.path.exists(f))

    def test_export_a_new_version(self):
        self._create_packages_and_builds()
        # Export an update of the same conans

        # Do not adjust cpu_count, it is reusing a cache
        client2 = TestClient(self.client.cache_folder, cpu_count=False)
        files2 = cpp_hello_conan_files("Hello0", "0.1")
        files2[CONANFILE] = "# insert comment\n %s" % files2[CONANFILE]
        client2.save(files2)
        client2.run("export . lasote/stable")

        reg_path3 = client2.cache.package_layout(self.ref).export()
        digest3 = FileTreeManifest.load(client2.cache.package_layout(self.ref).export())

        self.assertIn('%s: A new conanfile.py version was exported' % str(self.ref),
                      self.client.out)
        self.assertIn('%s: Folder: %s' % (str(self.ref), reg_path3), self.client.out)

        self.assertTrue(os.path.exists(reg_path3))

        for name in list(files2.keys()):
            self.assertTrue(os.path.exists(os.path.join(reg_path3, name)))

        expected_sums = {'hello.cpp': '4f005274b2fdb25e6113b69774dac184',
                         'main.cpp': '0479f3c223c9a656a718f3148e044124',
                         'CMakeLists.txt': '10d907c160c360b28f6991397a5aa9b4',
                         'conanfile.py': 'ad17cf00b3142728b03ac37782b9acd9',
                         'executable': '68b329da9893e34099c7d8ad5cb9c940',
                         'helloHello0.h': '9448df034392fc8781a47dd03ae71bdd'}
        self.assertEqual(expected_sums, digest3.file_sums)

        # for f in file_list:
        #    self.assertFalse(os.path.exists(f))

    def _create_packages_and_builds(self):
        reg_builds = self.client.cache.package_layout(self.ref).builds()
        reg_packs = self.client.cache.package_layout(self.ref).packages()

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


class ExportMetadataTest(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Lib(ConanFile):
            revision_mode = "{revision_mode}"
    """)

    summary_hash = "bfe8b4a6a2a74966c0c4e0b34705004a"

    def test_revision_mode_hash(self):
        t = TestClient()
        t.save({'conanfile.py': self.conanfile.format(revision_mode="hash")})

        ref = ConanFileReference.loads("name/version@user/channel")
        t.run("export . {}".format(ref))

        meta = t.cache.package_layout(ref, short_paths=False).load_metadata()
        self.assertEqual(meta.recipe.revision, self.summary_hash)

    def test_revision_mode_scm(self):
        path, rev = create_local_git_repo(
            files={'conanfile.py': self.conanfile.format(revision_mode="scm")})
        t = TestClient(current_folder=path)

        ref = ConanFileReference.loads("name/version@user/channel")
        t.run("export . {}".format(ref))

        meta = t.cache.package_layout(ref, short_paths=False).load_metadata()
        self.assertEqual(meta.recipe.revision, rev)

    def test_revision_mode_invalid(self):
        conanfile = self.conanfile.format(revision_mode="auto")

        t = TestClient()
        t.save({'conanfile.py': conanfile})
        ref = ConanFileReference.loads("name/version@user/channel")
        t.run("export . {}".format(ref), assert_error=True)
        self.assertIn("ERROR: Revision mode should be one of 'hash' (default) or 'scm'", t.out)

    def test_export_no_params(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
                        from conans import ConanFile

                        class MyPkg(ConanFile):
                            name = "lib"
                            version = "1.0"
                        """)
        client.save({"conanfile.py": conanfile})
        client.run('export .')
        client.cache.package_layout(ConanFileReference.loads("lib/1.0@")).export()
        self.assertIn("lib/1.0: A new conanfile.py version was exported", client.out)

        # Do it twice
        client.run('export . ')
        self.assertIn("lib/1.0: The stored package has not changed", client.out)

    def export_with_name_and_version_test(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
                from conans import ConanFile

                class MyPkg(ConanFile):
                    pass
                """)
        client.save({"conanfile.py": conanfile})

        client.run('export . lib/1.0@')
        self.assertIn("lib/1.0: A new conanfile.py version was exported", client.out)

    def export_with_only_user_channel_test(self):
        """This should be the recommended way and only from Conan 2.0"""
        client = TestClient()
        conanfile = textwrap.dedent("""
                from conans import ConanFile

                class MyPkg(ConanFile):
                    name = "lib"
                    version = "1.0"
                """)
        client.save({"conanfile.py": conanfile})

        client.run('export . @user/channel')
        self.assertIn("lib/1.0@user/channel: A new conanfile.py version was exported", client.out)
