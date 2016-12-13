import unittest
from conans.test.tools import TestClient
import os
from conans.client.importer import IMPORTS_MANIFESTS
from conans.util.files import load
from conans.model.manifest import FileTreeManifest


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
        self.client.run("export lasote/stable")

    def imports_error_test(self):
        self.client.save({"conanfile.txt": test1}, clean_first=True)
        self.client.run("install --no-imports")
        self.assertNotIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertNotIn("file2.txt", os.listdir(self.client.current_folder))

        error = self.client.run("imports", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("conanbuildinfo.txt file not found", self.client.user_io.out)

    def install_manifest_test(self):
        self.client.save({"conanfile.txt": test1}, clean_first=True)
        self.client.run("install -g txt")
        self.assertIn("imports(): Copied 2 '.txt' files", self.client.user_io.out)
        self.assertIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertIn("file2.txt", os.listdir(self.client.current_folder))
        self._check_manifest()

    def undo_install_manifest_test(self):
        self.client.save({"conanfile.txt": test1}, clean_first=True)
        self.client.run("install -g txt")
        self.client.run("imports --undo")
        self.assertNotIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertNotIn("file2.txt", os.listdir(self.client.current_folder))
        self.assertNotIn(IMPORTS_MANIFESTS, os.listdir(self.client.current_folder))
        self.assertIn("Removed 2 imported files", self.client.user_io.out)
        self.assertIn("Removed imports manifest file", self.client.user_io.out)

    def _check_manifest(self):
        manifest_content = load(os.path.join(self.client.current_folder, IMPORTS_MANIFESTS))
        manifest = FileTreeManifest.loads(manifest_content)
        self.assertEqual(manifest.file_sums,
                         {os.path.join(self.client.current_folder, "file1.txt"):
                          "8b1a9953c4611296a827abf8c47804d7",
                          os.path.join(self.client.current_folder, "file2.txt"):
                          "f5a7924e621e84c9280a9a27e1bcb7f6"})

    def imports_test(self):
        self.client.save({"conanfile.txt": test1}, clean_first=True)
        self.client.run("install --no-imports -g txt")
        self.assertNotIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertNotIn("file2.txt", os.listdir(self.client.current_folder))
        self.client.run("imports")
        self.assertIn("imports(): Copied 2 '.txt' files", self.client.user_io.out)
        self.assertIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertIn("file2.txt", os.listdir(self.client.current_folder))
        self._check_manifest()

    def imports_filename_test(self):
        self.client.save({"conanfile.txt": test1,
                          "conanfile.py": test2,
                          "conanfile2.py": test3}, clean_first=True)
        self.client.run("install --no-imports -g txt")
        self.assertNotIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertNotIn("file2.txt", os.listdir(self.client.current_folder))

        self.client.run("imports -f=conanfile2.py")
        self.assertNotIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertIn("file2.txt", os.listdir(self.client.current_folder))

        os.unlink(os.path.join(self.client.current_folder, "file2.txt"))
        self.client.run("imports")
        self.assertIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertNotIn("file2.txt", os.listdir(self.client.current_folder))

        os.unlink(os.path.join(self.client.current_folder, "file1.txt"))
        self.client.run("imports -f conanfile.txt")
        self.assertIn("file1.txt", os.listdir(self.client.current_folder))
        self.assertIn("file2.txt", os.listdir(self.client.current_folder))
