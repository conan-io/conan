import os
import textwrap
import unittest

from conans.client.importer import IMPORTS_MANIFESTS
from conans.model.manifest import FileTreeManifest
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import mkdir

conanfile = """
from conans import ConanFile
from conans.util.files import save

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    build_policy = "missing"

    def build(self):
        save("file1.txt", "Hello")
        save("file2.txt", "World")

    def package(self):
        self.copy("file1.txt")
        self.copy("file2.txt")
"""

test1 = """[requires]
Hello/0.1@lasote/stable

[imports]
., file* -> .
"""

test2 = """
from conans import ConanFile
from conans.util.files import save

class HelloReuseConan(ConanFile):
    requires = "Hello/0.1@lasote/stable"

    def imports(self):
        self.copy("*1.txt")
"""

test3 = """
from conans import ConanFile
from conans.util.files import save

class HelloReuseConan(ConanFile):
    requires = "Hello/0.1@lasote/stable"

    def imports(self):
        self.copy("*2.txt")
"""


class ImportsTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        self.client.save({"conanfile.py": conanfile})
        self.client.run("export . lasote/stable")

    def test_imports_global_path_removed(self):
        """ Ensure that when importing files in a global path, outside the package build,
        they are removed too
        """
        dst_global_folder = temp_folder().replace("\\", "/")
        conanfile2 = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "Say"
    version = "0.1"
    requires = "Hello/0.1@lasote/stable"

    def imports(self):
        self.copy("file*.txt", dst="%s")
''' % dst_global_folder

        self.client.save({"conanfile.py": conanfile2}, clean_first=True)
        self.client.run("export . lasote/stable")

        self.client.current_folder = temp_folder()
        self.client.run("install Say/0.1@lasote/stable --build=missing")
        for filename in ["file1.txt", "file2.txt"]:
            self.assertFalse(os.path.exists(os.path.join(dst_global_folder, filename)))

    def test_imports_env_var(self):
        conanfile2 = '''
from conans import ConanFile
import os

class ConanLib(ConanFile):
    requires = "Hello/0.1@lasote/stable"

    def imports(self):
        self.copy("file*.txt", dst=os.environ["MY_IMPORT_PATH"])
'''
        for folder in ("folder1", "folder2"):
            self.client.save({"conanfile.py": conanfile2}, clean_first=True)
            self.client.run("install conanfile.py -e MY_IMPORT_PATH=%s" % folder)
            self.assertEqual("Hello",
                             self.client.load(os.path.join(folder, "file1.txt")))

    def test_imports_error(self):
        self.client.save({"conanfile.txt": test1}, clean_first=True)
        self.client.run("install . --no-imports")
        self.assertNotIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertNotIn("file2.txt", os.listdir(self.client.current_folder))

        self.client.run("imports .")  # Automatic conanbuildinfo.txt
        self.assertNotIn("conanbuildinfo.txt file not found", self.client.out)

    def test_install_manifest(self):
        self.client.save({"conanfile.txt": test1}, clean_first=True)
        self.client.run("install ./conanfile.txt")
        self.assertIn("imports(): Copied 2 '.txt' files", self.client.out)
        self.assertIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertIn("file2.txt", os.listdir(self.client.current_folder))
        self._check_manifest()

    def test_install_manifest_without_install(self):
        self.client.save({"conanfile.txt": test1}, clean_first=True)
        self.client.run('imports . ', assert_error=True)
        self.assertIn("You can generate it using 'conan install'", self.client.out)

    def test_install_dest(self):
        self.client.save({"conanfile.txt": test1}, clean_first=True)
        self.client.run("install ./ --no-imports")
        self.assertNotIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertNotIn("file2.txt", os.listdir(self.client.current_folder))

        self.client.run("imports . -imf myfolder")
        files = os.listdir(os.path.join(self.client.current_folder, "myfolder"))
        self.assertIn("file1.txt", files)
        self.assertIn("file2.txt", files)

    def test_imports_build_folder(self):
        self.client.save({"conanfile.txt": test1}, clean_first=True)
        tmp = self.client.current_folder
        self.client.current_folder = os.path.join(self.client.current_folder, "build")
        mkdir(self.client.current_folder)
        self.client.run("install .. --no-imports")
        self.client.current_folder = tmp
        self.client.run("imports . --install-folder=build --import-folder=.")
        files = os.listdir(self.client.current_folder)
        self.assertIn("file1.txt", files)
        self.assertIn("file2.txt", files)

    def test_install_abs_dest(self):
        self.client.save({"conanfile.txt": test1}, clean_first=True)
        self.client.run("install . --no-imports")
        self.assertNotIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertNotIn("file2.txt", os.listdir(self.client.current_folder))

        tmp_folder = temp_folder()
        self.client.run('imports . -imf "%s"' % tmp_folder)
        files = os.listdir(tmp_folder)
        self.assertIn("file1.txt", files)
        self.assertIn("file2.txt", files)

    def test_undo_install_manifest(self):
        self.client.save({"conanfile.txt": test1}, clean_first=True)
        self.client.run("install conanfile.txt")
        self.client.run("imports . --undo")
        self.assertNotIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertNotIn("file2.txt", os.listdir(self.client.current_folder))
        self.assertNotIn(IMPORTS_MANIFESTS, os.listdir(self.client.current_folder))
        self.assertIn("Removed 2 imported files", self.client.out)
        self.assertIn("Removed imports manifest file", self.client.out)

    def _check_manifest(self):
        manifest_content = self.client.load(IMPORTS_MANIFESTS)
        manifest = FileTreeManifest.loads(manifest_content)
        self.assertEqual(manifest.file_sums,
                         {os.path.join(self.client.current_folder, "file1.txt"):
                          "8b1a9953c4611296a827abf8c47804d7",
                          os.path.join(self.client.current_folder, "file2.txt"):
                          "f5a7924e621e84c9280a9a27e1bcb7f6"})

    def test_imports(self):
        self.client.save({"conanfile.txt": test1}, clean_first=True)
        self.client.run("install . --no-imports -g txt")
        self.assertNotIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertNotIn("file2.txt", os.listdir(self.client.current_folder))
        self.client.run("imports .")
        self.assertIn("imports(): Copied 2 '.txt' files", self.client.out)
        self.assertIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertIn("file2.txt", os.listdir(self.client.current_folder))
        self._check_manifest()

    def test_imports_filename(self):
        self.client.save({"conanfile.txt": test1,
                          "conanfile.py": test2,
                          "conanfile2.py": test3}, clean_first=True)
        self.client.run("install . --no-imports")
        self.assertNotIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertNotIn("file2.txt", os.listdir(self.client.current_folder))

        self.client.run("imports conanfile2.py")
        self.assertNotIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertIn("file2.txt", os.listdir(self.client.current_folder))

        os.unlink(os.path.join(self.client.current_folder, "file2.txt"))
        self.client.run("imports .")
        self.assertIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertNotIn("file2.txt", os.listdir(self.client.current_folder))

        os.unlink(os.path.join(self.client.current_folder, "file1.txt"))
        self.client.run("imports ./conanfile.txt")
        self.assertIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertIn("file2.txt", os.listdir(self.client.current_folder))


class SymbolicImportsTest(unittest.TestCase):
    """ Tests to cover the functionality of importing from @bindirs, @libdirs, etc
    """
    def setUp(self):
        pkg = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                exports = "*"
                def package(self):
                    self.copy("*.bin", "mybin")  # USE DIFFERENT FOLDERS
                    self.copy("*.lib", "mylib")
                    self.copy("*.a", "myotherlib")
                def package_info(self):
                    self.cpp_info.bindirs = ["mybin"]
                    self.cpp_info.libdirs = ["mylib", "myotherlib"]
            """)
        self.client = TestClient()
        self.client.save({"conanfile.py": pkg,
                          "myfile.bin": "hello world",
                          "myfile.lib": "bye world",
                          "myfile.a": "bye moon"})
        consumer = textwrap.dedent("""
            from conans import ConanFile, load
            class Pkg(ConanFile):
                requires = "pkg/0.1"
                def build(self):
                    self.output.info("MSG: %s" % load("myfile.txt"))
                def imports(self):
                    self.copy("*", src="@bindirs", dst="bin")
                    self.copy("*", src="@libdirs", dst="lib")
            """)
        self.consumer = TestClient(cache_folder=self.client.cache_folder)
        self.consumer.save({"conanfile.py": consumer}, clean_first=True)

    def test_imports_symbolic_names(self):
        self.client.run("create . pkg/0.1@")
        self.consumer.run("install .")
        self.assertEqual("hello world", self.consumer.load("bin/myfile.bin"))
        self.assertEqual("bye world", self.consumer.load("lib/myfile.lib"))
        self.assertEqual("bye moon", self.consumer.load("lib/myfile.a"))

    def test_error_unknown(self):
        self.client.run("create . pkg/0.1@")
        consumer = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                requires = "pkg/0.1"
                def imports(self):
                    self.copy("*", src="@unknown_unexisting_dir", dst="bin")
            """)
        self.consumer.save({"conanfile.py": consumer}, clean_first=True)
        self.consumer.run("install .", assert_error=True)
        self.assertIn("Import from unknown package folder '@unknown_unexisting_dir'",
                      self.consumer.out)

    def test_imports_symbolic_from_editable(self):
        layout = textwrap.dedent("""
            [libdirs]
            .
            [bindirs]
            .
            """)
        self.client.save({"layout": layout})
        self.client.run("editable add . pkg/0.1@ --layout=layout")
        self.consumer.run("install .")
        self.assertEqual("hello world", self.consumer.load("bin/myfile.bin"))
        self.assertEqual("bye world", self.consumer.load("lib/myfile.lib"))
        self.assertEqual("bye moon", self.consumer.load("lib/myfile.a"))


class SymbolicImportsComponentTest(unittest.TestCase):
    """ Tests to cover the functionality of importing from @bindirs, @libdirs, etc
        with components.
    """
    def setUp(self):
        pkg = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                exports = "*"
                def package(self):
                    self.copy("*A.bin", "binA")  # USE DIFFERENT FOLDERS
                    self.copy("*B.bin", "binB")
                    self.copy("*A.lib", "libA")
                    self.copy("*B.lib", "libB")
                def package_info(self):
                    self.cpp_info.components["A"].bindirs = ["binA"]
                    self.cpp_info.components["A"].libdirs = ["libA"]
                    self.cpp_info.components["B"].bindirs = ["binB"]
                    self.cpp_info.components["B"].libdirs = ["libB"]
            """)
        self.client = TestClient()
        self.client.save({"conanfile.py": pkg,
                          "myfileA.bin": "hello world",
                          "myfileB.bin": "hello moon",
                          "myfileA.lib": "bye world",
                          "myfileB.lib": "bye moon"})
        consumer = textwrap.dedent("""
            from conans import ConanFile, load
            class Pkg(ConanFile):
                requires = "pkg/0.1"
                def build(self):
                    self.output.info("MSG: %s" % load("myfile.txt"))
                def imports(self):
                    self.copy("*", src="@bindirs", dst="bin")
                    self.copy("*", src="@libdirs", dst="lib")
            """)
        self.consumer = TestClient(cache_folder=self.client.cache_folder)
        self.consumer.save({"conanfile.py": consumer}, clean_first=True)

    def test_imports_symbolic_names(self):
        self.client.run("create . pkg/0.1@")
        self.consumer.run("install .")
        self.assertEqual("hello world", self.consumer.load("bin/myfileA.bin"))
        self.assertEqual("hello moon", self.consumer.load("bin/myfileB.bin"))
        self.assertEqual("bye world", self.consumer.load("lib/myfileA.lib"))
        self.assertEqual("bye moon", self.consumer.load("lib/myfileB.lib"))
