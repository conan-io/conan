import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import save_files, load


class ExportsMethodTest(unittest.TestCase):

    def test_export_method(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class MethodConan(ConanFile):
                exports = "file.txt"
                def export(self):
                    self.copy("LICENSE.md")
            """)
        client.save({"conanfile.py": conanfile, "LICENSE.md": "license", "file.txt": "file"})
        client.run("export . pkg/0.1@")
        self.assertIn("pkg/0.1: Calling export()", client.out)
        self.assertIn("pkg/0.1 exports: Copied 1 '.txt' file: file.txt", client.out)
        self.assertIn("pkg/0.1 export() method: Copied 1 '.md' file: LICENSE.md", client.out)

        layout = client.cache.package_layout(ConanFileReference.loads("pkg/0.1"))
        exported_files = os.listdir(layout.export())
        self.assertIn("file.txt", exported_files)
        self.assertIn("LICENSE.md", exported_files)

    def test_export_method_parent_folder(self):
        folder = temp_folder()
        save_files(folder, {"subdir/subdir2/file2.txt": "", "subdir/file1.txt": ""})
        client = TestClient(current_folder=os.path.join(folder, "recipe"))
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class MethodConan(ConanFile):
                def export(self):
                    self.output.info("Executing export() method")
                    self.copy("*.txt", src="../subdir")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . pkg/0.1@")
        self.assertIn("pkg/0.1 export() method: Copied 2 '.txt' files: file1.txt, file2.txt",
                      client.out)

        layout = client.cache.package_layout(ConanFileReference.loads("pkg/0.1"))
        self.assertTrue(os.path.isfile(os.path.join(layout.export(), "file1.txt")))
        self.assertTrue(os.path.isfile(os.path.join(layout.export(), "subdir2", "file2.txt")))

    def test_export_no_settings_options_method(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class MethodConan(ConanFile):
                settings = "os"
                def export(self):
                    if self.settings.os == "Windows":
                        self.copy("LICENSE.md")
            """)
        client.save({"conanfile.py": conanfile, "LICENSE.md": "license"})
        client.run("export . pkg/0.1@", assert_error=True)
        self.assertIn("ERROR: pkg/0.1: Error in export() method, line 7", client.out)

        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class MethodConan(ConanFile):
                default_options = {"myopt": "myval"}
                def export(self):
                    if self.default_options["myopt"] == "myval":
                        self.copy("LICENSE.md")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . pkg/0.1@", assert_error=True)
        self.assertIn("ERROR: pkg/0.1: Error in export() method, line 7", client.out)

        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class MethodConan(ConanFile):
                options = {"myopt": ["myval"]}
                default_options = {"myopt": "myval"}
                def export(self):
                    pass
                def export_sources(self):
                    pass
                def build(self):
                    self.output.info("MYOPT: %s" % self.options.myopt)
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/0.1@")
        self.assertIn("pkg/0.1: MYOPT: myval", client.out)

    def test_export_folders(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
           from conans import ConanFile
           from conans.tools import save, load
           import os

           class MethodConan(ConanFile):
               def export(self):
                   content = load(os.path.join(os.getcwd(), "data.txt"))
                   save(os.path.join(self.export_folder, "myfile.txt"), content)
           """)
        client.save({"recipe/conanfile.py": conanfile, "recipe/data.txt": "mycontent"})
        client.run("export recipe pkg/0.1@")
        layout = client.cache.package_layout(ConanFileReference.loads("pkg/0.1"))
        self.assertEqual("mycontent", load(os.path.join(layout.export(), "myfile.txt")))
        client.current_folder = os.path.join(client.current_folder, "recipe")
        client.run("export . pkg/0.1@")
        layout = client.cache.package_layout(ConanFileReference.loads("pkg/0.1"))
        self.assertEqual("mycontent", load(os.path.join(layout.export(), "myfile.txt")))

    def test_export_attribute_error(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MethodConan(ConanFile):
                export = "file.txt"
            """)
        client.save({"conanfile.py": conanfile, "file.txt": "file"})
        client.run("export . pkg/0.1@", assert_error=True)
        self.assertIn("ERROR: conanfile 'export' must be a method", client.out)

    def test_exports_method_error(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MethodConan(ConanFile):
                def exports(self):
                    pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . pkg/0.1@", assert_error=True)
        self.assertIn("ERROR: conanfile 'exports' shouldn't be a method, use 'export()' instead",
                      client.out)


class ExportsSourcesMethodTest(unittest.TestCase):

    def test_export_sources_method(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class MethodConan(ConanFile):
                exports_sources = "file.txt"
                def export_sources(self):
                    self.copy("LICENSE.md")
            """)
        client.save({"conanfile.py": conanfile, "LICENSE.md": "license", "file.txt": "file"})
        client.run("export . pkg/0.1@")
        self.assertIn("pkg/0.1 exports_sources: Copied 1 '.txt' file: file.txt", client.out)
        self.assertIn("pkg/0.1 export_sources() method: Copied 1 '.md' file: LICENSE.md", client.out)

        layout = client.cache.package_layout(ConanFileReference.loads("pkg/0.1"))
        exported_files = os.listdir(layout.export_sources())
        self.assertIn("file.txt", exported_files)
        self.assertIn("LICENSE.md", exported_files)

    def test_export_source_folders(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
           from conans import ConanFile
           from conans.tools import save, load
           import os

           class MethodConan(ConanFile):
               def export_sources(self):
                   content = load(os.path.join(os.getcwd(), "data.txt"))
                   save(os.path.join(self.export_sources_folder, "myfile.txt"), content)
           """)
        client.save({"recipe/conanfile.py": conanfile, "recipe/data.txt": "mycontent"})
        client.run("export recipe pkg/0.1@")
        layout = client.cache.package_layout(ConanFileReference.loads("pkg/0.1"))
        self.assertEqual("mycontent", load(os.path.join(layout.export_sources(), "myfile.txt")))
        client.current_folder = os.path.join(client.current_folder, "recipe")
        client.run("export . pkg/0.1@")
        layout = client.cache.package_layout(ConanFileReference.loads("pkg/0.1"))
        self.assertEqual("mycontent", load(os.path.join(layout.export_sources(), "myfile.txt")))

    def test_export_sources_attribute_error(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MethodConan(ConanFile):
                export_sources = "file.txt"
            """)
        client.save({"conanfile.py": conanfile, "file.txt": "file"})
        client.run("export . pkg/0.1@", assert_error=True)
        self.assertIn("ERROR: conanfile 'export_sources' must be a method", client.out)

    def test_exports_sources_method_error(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MethodConan(ConanFile):
                def exports_sources(self):
                    pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . pkg/0.1@", assert_error=True)
        self.assertIn("ERROR: conanfile 'exports_sources' shouldn't be a method, "
                      "use 'export_sources()' instead", client.out)

    def test_exports_sources_upload_error(self):
        # https://github.com/conan-io/conan/issues/7377
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            from conans import ConanFile, tools

            class MethodConan(ConanFile):
                def export_sources(self):
                    self.copy("*")
                def build(self):
                    self.output.info("CONTENT: %s" % tools.load("myfile.txt"))
            """)
        client.save({"conanfile.py": conanfile,
                     "myfile.txt": "mycontent"})
        client.run("export . pkg/0.1@")
        self.assertIn("pkg/0.1 export_sources() method: Copied 1 '.txt' file: myfile.txt",
                      client.out)
        client.run("upload pkg/0.1@")
        client.run("remove * -f")
        client.run("install pkg/0.1@ --build")
        self.assertIn("Downloading conan_sources.tgz", client.out)
        self.assertIn("pkg/0.1: CONTENT: mycontent", client.out)
