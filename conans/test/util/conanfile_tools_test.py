import unittest
import os
from conans.util.files import save, load
from conans.client.loader import ConanFileLoader, ProcessedProfile
from conans.test.utils.test_files import temp_folder
from conans import tools
from parameterized.parameterized import parameterized
from conans.test.utils.tools import TestClient
from conans.client.graph.python_requires import ConanPythonRequire


base_conanfile = '''
from conans import ConanFile
from conans.tools import patch, replace_in_file
import os

class ConanFileToolsTest(ConanFile):
    name = "test"
    version = "1.9.10"
'''


class ConanfileToolsTest(unittest.TestCase):

    def save_append_test(self):
        # https://github.com/conan-io/conan/issues/2841 (regression)
        client = TestClient()
        conanfile = """from conans import ConanFile
from conans.tools import save
class Pkg(ConanFile):
    def source(self):
        save("myfile.txt", "Hello", append=True)
"""
        client.save({"conanfile.py": conanfile,
                     "myfile.txt": "World"})
        client.run("source .")
        self.assertEqual("WorldHello",
                         load(os.path.join(client.current_folder, "myfile.txt")))

    def test_untar(self):
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "example.txt")
        save(file_path, "Hello world!")
        tar_path = os.path.join(tmp_dir, "sample.tar")
        try:
            old_path = os.getcwd()
            os.chdir(tmp_dir)
            import tarfile
            tar = tarfile.open(tar_path, "w")
            tar.add("example.txt")
            tar.close()
        finally:
            os.chdir(old_path)
        output_dir = os.path.join(tmp_dir, "output_dir")
        tools.unzip(tar_path, output_dir)
        content = load(os.path.join(output_dir, "example.txt"))
        self.assertEqual(content, "Hello world!")

    def test_replace_in_file(self):
        file_content = base_conanfile + '''
    def build(self):
        replace_in_file("text.txt", "ONE TWO THREE", "FOUR FIVE SIX")
'''
        tmp_dir, file_path, text_file = self._save_files(file_content)
        self._build_and_check(tmp_dir, file_path, text_file, "FOUR FIVE SIX")

    @parameterized.expand([(0, ), (1, )])
    def test_patch_from_file(self, strip):
        if strip:
            file_content = base_conanfile + '''
    def build(self):
        patch(patch_file="file.patch", strip=%s)
''' % strip
            patch_content = '''--- %s/text.txt\t2016-01-25 17:57:11.452848309 +0100
+++ %s/text_new.txt\t2016-01-25 17:57:28.839869950 +0100
@@ -1 +1 @@
-ONE TWO THREE
+ONE TWO FOUR''' % ("old_path", "new_path")
        else:
            file_content = base_conanfile + '''
    def build(self):
        patch(patch_file="file.patch")
'''
            patch_content = '''--- text.txt\t2016-01-25 17:57:11.452848309 +0100
+++ text_new.txt\t2016-01-25 17:57:28.839869950 +0100
@@ -1 +1 @@
-ONE TWO THREE
+ONE TWO FOUR'''

        tmp_dir, file_path, text_file = self._save_files(file_content)
        patch_file = os.path.join(tmp_dir, "file.patch")
        save(patch_file, patch_content)
        self._build_and_check(tmp_dir, file_path, text_file, "ONE TWO FOUR")

    def test_patch_from_str(self):
        file_content = base_conanfile + '''
    def build(self):
        patch_content = \'''--- text.txt\t2016-01-25 17:57:11.452848309 +0100
+++ text_new.txt\t2016-01-25 17:57:28.839869950 +0100
@@ -1 +1 @@
-ONE TWO THREE
+ONE TWO DOH!\'''
        patch(patch_string=patch_content)

'''
        tmp_dir, file_path, text_file = self._save_files(file_content)
        self._build_and_check(tmp_dir, file_path, text_file, "ONE TWO DOH!")

    def test_patch_new_delete(self):
        conanfile = base_conanfile + '''
    def build(self):
        from conans.tools import load, save
        save("oldfile", "legacy code")
        assert(os.path.exists("oldfile"))
        patch_content = """--- /dev/null
+++ b/newfile
@@ -0,0 +0,3 @@
+New file!
+New file!
+New file!
--- a/oldfile
+++ b/dev/null
@@ -0,1 +0,0 @@
-legacy code
"""
        patch(patch_string=patch_content)
        self.output.info("NEW FILE=%s" % load("newfile"))
        self.output.info("OLD FILE=%s" % os.path.exists("oldfile"))
'''
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . user/testing")
        self.assertIn("test/1.9.10@user/testing: NEW FILE=New file!\nNew file!\nNew file!\n",
                      client.out)
        self.assertIn("test/1.9.10@user/testing: OLD FILE=False", client.out)

    def test_error_patch(self):
        file_content = base_conanfile + '''
    def build(self):
        patch_content = "some corrupted patch"
        patch(patch_string=patch_content, output=self.output)

'''
        client = TestClient()
        client.save({"conanfile.py": file_content})
        client.run("install .")
        error = client.run("build .", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("patch: error: no patch data found!", client.user_io.out)
        self.assertIn("ERROR: test/1.9.10@PROJECT: Error in build() method, line 12",
                      client.user_io.out)
        self.assertIn("Failed to parse patch: string", client.user_io.out)

    def _save_files(self, file_content):
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "conanfile.py")
        text_file = os.path.join(tmp_dir, "text.txt")
        save(file_path, file_content)
        save(text_file, "ONE TWO THREE")
        return tmp_dir, file_path, text_file

    def _build_and_check(self, tmp_dir, file_path, text_file, msg):
        loader = ConanFileLoader(None, None, ConanPythonRequire(None, None))
        ret = loader.load_conanfile(file_path, None, ProcessedProfile())
        curdir = os.path.abspath(os.curdir)
        os.chdir(tmp_dir)
        try:
            ret.build()
        finally:
            os.chdir(curdir)

        content = load(text_file)
        self.assertEquals(content, msg)
