import os
import unittest
from textwrap import dedent

from parameterized.parameterized import parameterized

from conans.client.graph.python_requires import ConanPythonRequire
from conans.client.loader import ConanFileLoader
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestBufferConanOutput,\
    test_processed_profile
from conans.util.files import save, load

base_conanfile = '''
from conans import ConanFile
from conans.tools import patch, replace_in_file
import os

class ConanFileToolsTest(ConanFile):
    name = "test"
    version = "1.9.10"
'''


class ToolsFilesPatchTest(unittest.TestCase):

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

    def test_patch_strip_new(self):
        conanfile = dedent("""
            from conans import ConanFile, tools
            class PatchConan(ConanFile):
                def source(self):
                    tools.patch(self.source_folder, "example.patch", strip=1)""")
        patch = dedent("""
            --- /dev/null
            +++ b/src/newfile
            @@ -0,0 +0,1 @@
            +New file!""")

        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "example.patch": patch})
        client.run("source .")
        self.assertEqual(load(os.path.join(client.current_folder, "newfile")),
                         "New file!")

    def test_patch_strip_delete(self):
        conanfile = dedent("""
            from conans import ConanFile, tools
            class PatchConan(ConanFile):
                def source(self):
                    tools.patch(self.source_folder, "example.patch", strip=1)""")
        patch = dedent("""
            --- a\src\oldfile
            +++ b/dev/null
            @@ -0,1 +0,0 @@
            -legacy code""")
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "example.patch": patch,
                     "oldfile": "legacy code"})
        path = os.path.join(client.current_folder, "oldfile")
        self.assertTrue(os.path.exists(path))
        client.run("source .")
        self.assertFalse(os.path.exists(path))

    def test_patch_strip_delete_no_folder(self):
        conanfile = dedent("""
            from conans import ConanFile, tools
            class PatchConan(ConanFile):
                def source(self):
                    tools.patch(self.source_folder, "example.patch", strip=1)""")
        patch = dedent("""
            --- a/oldfile
            +++ b/dev/null
            @@ -0,1 +0,0 @@
            -legacy code""")
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "example.patch": patch,
                     "oldfile": "legacy code"})
        path = os.path.join(client.current_folder, "oldfile")
        self.assertTrue(os.path.exists(path))
        client.run("source .")
        self.assertFalse(os.path.exists(path))

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

    def test_patch_new_strip(self):
        conanfile = base_conanfile + '''
    def build(self):
        from conans.tools import load, save
        patch_content = """--- /dev/null
+++ b/newfile
@@ -0,0 +0,3 @@
+New file!
+New file!
+New file!
"""
        patch(patch_string=patch_content, strip=1)
        self.output.info("NEW FILE=%s" % load("newfile"))
'''
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . user/testing")
        self.assertIn("test/1.9.10@user/testing: NEW FILE=New file!\nNew file!\nNew file!\n",
                      client.out)

    def test_error_patch(self):
        file_content = base_conanfile + '''
    def build(self):
        patch_content = "some corrupted patch"
        patch(patch_string=patch_content, output=self.output)

'''
        client = TestClient()
        client.save({"conanfile.py": file_content})
        client.run("install .")
        client.run("build .", assert_error=True)
        self.assertIn("patch: error: no patch data found!", client.out)
        self.assertIn("ERROR: conanfile.py (test/1.9.10): "
                      "Error in build() method, line 12", client.out)
        self.assertIn("Failed to parse patch: string", client.out)

    def _save_files(self, file_content):
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "conanfile.py")
        text_file = os.path.join(tmp_dir, "text.txt")
        save(file_path, file_content)
        save(text_file, "ONE TWO THREE")
        return tmp_dir, file_path, text_file

    def _build_and_check(self, tmp_dir, file_path, text_file, msg):
        loader = ConanFileLoader(None, TestBufferConanOutput(), ConanPythonRequire(None, None))
        ret = loader.load_consumer(file_path, test_processed_profile())
        curdir = os.path.abspath(os.curdir)
        os.chdir(tmp_dir)
        try:
            ret.build()
        finally:
            os.chdir(curdir)

        content = load(text_file)
        self.assertEqual(content, msg)
