import os
import unittest
from textwrap import dedent

from parameterized.parameterized import parameterized

from conans.client.loader import ConanFileLoader
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conans.util.files import save, load

base_conanfile = '''
from conan import ConanFile
from conan.tools.files import patch, replace_in_file
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
        patch(self, patch_file="file.patch", strip=%s)
''' % strip
            patch_content = '''--- %s/text.txt\t2016-01-25 17:57:11.452848309 +0100
+++ %s/text_new.txt\t2016-01-25 17:57:28.839869950 +0100
@@ -1 +1 @@
-ONE TWO THREE
+ONE TWO FOUR''' % ("old_path", "new_path")
        else:
            file_content = base_conanfile + '''
    def build(self):
        patch(self, patch_file="file.patch")
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
        patch(self, patch_string=patch_content)

'''
        tmp_dir, file_path, text_file = self._save_files(file_content)
        self._build_and_check(tmp_dir, file_path, text_file, "ONE TWO DOH!")

    def test_patch_strip_new(self):
        conanfile = dedent("""
            from conan import ConanFile
            from conan.tools.files import patch
            class PatchConan(ConanFile):
                def source(self):
                    patch(self, self.source_folder, "example.patch", strip=1)""")
        patch = dedent("""
            --- /dev/null
            +++ b/src/newfile
            @@ -0,0 +0,1 @@
            +New file!""")

        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "example.patch": patch})
        client.run("source .")
        self.assertEqual(client.load("newfile"), "New file!")

    def test_patch_strip_delete(self):
        conanfile = dedent("""
            from conan import ConanFile
            from conan.tools.files import patch
            class PatchConan(ConanFile):
                def source(self):
                    patch(self, self.source_folder, "example.patch", strip=1)""")
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
            from conan import ConanFile
            from conan.tools.files import patch
            class PatchConan(ConanFile):
                def source(self):
                    patch(self, self.source_folder, "example.patch", strip=1)""")
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
        from conan.tools.files import load, save
        save(self, "oldfile", "legacy code")
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
        patch(self, patch_string=patch_content)
        self.output.info("NEW FILE=%s" % load(self, "newfile"))
        self.output.info("OLD FILE=%s" % os.path.exists("oldfile"))
'''
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . --user=user --channel=testing")
        self.assertIn("test/1.9.10@user/testing: NEW FILE=New file!\nNew file!\nNew file!\n",
                      client.out)
        self.assertIn("test/1.9.10@user/testing: OLD FILE=False", client.out)

    def test_patch_new_strip(self):
        conanfile = base_conanfile + '''
    def build(self):
        from conan.tools.files import load, save
        patch_content = """--- /dev/null
+++ b/newfile
@@ -0,0 +0,3 @@
+New file!
+New file!
+New file!
"""
        patch(self, patch_string=patch_content, strip=1)
        self.output.info("NEW FILE=%s" % load(self, "newfile"))
'''
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . --user=user --channel=testing")
        self.assertIn("test/1.9.10@user/testing: NEW FILE=New file!\nNew file!\nNew file!\n",
                      client.out)

    def test_error_patch(self):
        file_content = base_conanfile + '''
    def build(self):
        patch_content = "some corrupted patch"
        patch(self, patch_string=patch_content, output=self.output)

'''
        client = TestClient()
        client.save({"conanfile.py": file_content})
        client.run("install .")
        client.run("build .", assert_error=True)
        self.assertIn("patch_ng: error: no patch data found!", client.out)
        self.assertIn("ERROR: conanfile.py (test/1.9.10): "
                      "Error in build() method, line 12", client.out)
        self.assertIn("Failed to parse patch: string", client.out)

    def test_add_new_file(self):
        """ Validate issue #5320
        """

        conanfile = dedent("""
            from conan import ConanFile
            from conan.tools.files import patch
            import os

            class ConanFileToolsTest(ConanFile):
                name = "foobar"
                version = "0.1.0"
                exports_sources = "*"

                def build(self):
                    patch(self, patch_file="add_files.patch")
                    assert os.path.isfile("foo.txt")
                    assert os.path.isfile("bar.txt")
        """)
        bar = "no creo en brujas"
        patch = dedent("""
            From c66347c66991b6e617d107b505c18b3115624b8a Mon Sep 17 00:00:00 2001
            From: Uilian Ries <uilianries@gmail.com>
            Date: Wed, 16 Oct 2019 14:31:34 -0300
            Subject: [PATCH] add foo

            ---
             bar.txt | 3 ++-
             foo.txt | 3 +++
             2 files changed, 5 insertions(+), 1 deletion(-)
             create mode 100644 foo.txt

            diff --git a/bar.txt b/bar.txt
            index 0f4ff3a..0bd3158 100644
            --- a/bar.txt
            +++ b/bar.txt
            @@ -1 +1,2 @@
            -no creo en brujas
            +Yo no creo en brujas, pero que las hay, las hay
            +
            diff --git a/foo.txt b/foo.txt
            new file mode 100644
            index 0000000..91e8c0d
            --- /dev/null
            +++ b/foo.txt
            @@ -0,0 +1,3 @@
            +For us, there is no spring.
            +Just the wind that smells fresh before the storm.
            +
            --
            2.23.0


        """)

        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "add_files.patch": patch,
                     "bar.txt": bar})
        client.run("install .")
        client.run("build .")
        bar_content = client.load("bar.txt")
        self.assertIn(dedent("""Yo no creo en brujas, pero que las hay, las hay
                             """), bar_content)
        foo_content = client.load("foo.txt")
        self.assertIn(dedent("""For us, there is no spring.
Just the wind that smells fresh before the storm."""), foo_content)
        self.assertIn("Calling build()", client.out)
        self.assertNotIn("Warning", client.out)

    def _save_files(self, file_content):
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "conanfile.py")
        text_file = os.path.join(tmp_dir, "text.txt")
        save(file_path, file_content)
        save(text_file, "ONE TWO THREE")
        return tmp_dir, file_path, text_file

    def _build_and_check(self, tmp_dir, file_path, text_file, msg):
        loader = ConanFileLoader(None)
        ret = loader.load_consumer(file_path)
        curdir = os.path.abspath(os.curdir)
        ret.folders.set_base_source(os.path.dirname(file_path))
        ret.folders.set_base_export_sources(os.path.dirname(file_path))
        os.chdir(tmp_dir)
        try:
            ret.build()
        finally:
            os.chdir(curdir)

        content = load(text_file)
        self.assertEqual(content, msg)

    def test_fuzzy_patch(self):
        conanfile = dedent("""
            from conan import ConanFile
            from conan.tools.files import patch
            import os

            class ConanFileToolsTest(ConanFile):
                name = "fuzz"
                version = "0.1.0"
                exports_sources = "*"

                def build(self):
                    patch(self, patch_file="fuzzy.patch", fuzz=True)
        """)
        source = dedent("""X
Y
Z""")
        patch = dedent("""diff --git a/Jamroot b/Jamroot
index a6981dd..0c08f09 100644
--- a/Jamroot
+++ b/Jamroot
@@ -1,3 +1,4 @@
 X
 YYYY
+V
 W""")
        expected = dedent("""X
Y
V
Z""")
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "fuzzy.patch": patch,
                     "Jamroot": source})
        client.run("install .")
        client.run("build .")
        content = client.load("Jamroot")
        self.assertIn(expected, content)
