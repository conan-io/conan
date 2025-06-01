import os
import textwrap

from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save_files, load


class TestExportsMethod:

    def test_export_method(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import copy

            class MethodConan(ConanFile):
                exports = "file.txt"
                def export(self):
                    copy(self, "LICENSE.md", self.recipe_folder, self.export_folder)
            """)
        client.save({"conanfile.py": conanfile, "LICENSE.md": "license", "file.txt": "file"})
        client.run("export . --name=pkg --version=0.1")
        assert "pkg/0.1: Copied 1 '.txt' file: file.txt" in client.out
        assert "pkg/0.1: Calling export()" in client.out
        assert "Copied 1 '.md' file: LICENSE.md" in client.out

        layout = client.exported_layout()

        exported_files = os.listdir(layout.export())
        assert "file.txt" in exported_files
        assert "LICENSE.md" in exported_files

    def test_export_method_parent_folder(self):
        folder = temp_folder()
        save_files(folder, {"subdir/subdir2/file2.txt": "", "subdir/file1.txt": ""})
        client = TestClient(current_folder=os.path.join(folder, "recipe"))
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import copy

            class MethodConan(ConanFile):
                def export(self):
                    self.output.info("Executing export() method")
                    copy(self, "*.txt", os.path.join(self.recipe_folder, "../subdir"),
                         self.export_folder)
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=0.1")
        assert "Copied 2 '.txt' files: file1.txt, file2.txt" in client.out

        layout = client.exported_layout()

        assert os.path.isfile(os.path.join(layout.export(), "file1.txt"))
        assert os.path.isfile(os.path.join(layout.export(), "subdir2", "file2.txt"))

    def test_export_no_settings_options_method(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import copy

            class MethodConan(ConanFile):
                settings = "os"
                def export(self):
                    if self.settings.os == "Windows":
                        copy(self, "LICENSE.md", self.recipe_folder, self.export_folder)
            """)
        client.save({"conanfile.py": conanfile, "LICENSE.md": "license"})
        client.run("export . --name=pkg --version=0.1", assert_error=True)
        assert "ERROR: pkg/0.1: Error in export() method, line 8" in client.out

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import copy

            class MethodConan(ConanFile):
                options = {"myopt": ["myval", "other"]}
                default_options = {"myopt": "myval"}
                def export(self):
                    if self.default_options["myopt"] == "myval":
                        copy(self, "LICENSE.md", self.recipe_folder, self.export_folder)
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=0.1", assert_error=True)
        assert "ERROR: pkg/0.1: Error in export() method, line 9" in client.out

        conanfile = textwrap.dedent("""
            from conan import ConanFile

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
        client.run("create . --name=pkg --version=0.1")
        assert "pkg/0.1: MYOPT: myval" in client.out

    def test_export_folders(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.tools.files import save, load
           import os

           class MethodConan(ConanFile):
               def export(self):
                   content = load(self, os.path.join(os.getcwd(), "data.txt"))
                   save(self, os.path.join(self.export_folder, "myfile.txt"), content)
           """)
        client.save({"recipe/conanfile.py": conanfile, "recipe/data.txt": "mycontent"})
        client.run("export recipe --name=pkg --version=0.1")
        layout = client.exported_layout()
        assert "mycontent" == load(os.path.join(layout.export(), "myfile.txt"))
        client.current_folder = os.path.join(client.current_folder, "recipe")
        client.run("export . --name=pkg --version=0.1")
        layout = client.exported_layout()
        assert "mycontent" == load(os.path.join(layout.export(), "myfile.txt"))

    def test_export_attribute_error(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class MethodConan(ConanFile):
                export = "file.txt"
            """)
        client.save({"conanfile.py": conanfile, "file.txt": "file"})
        client.run("export . --name=pkg --version=0.1", assert_error=True)
        assert "ERROR: conanfile 'export' must be a method" in client.out

    def test_exports_method_error(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class MethodConan(ConanFile):
                def exports(self):
                    pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=0.1", assert_error=True)
        assert "ERROR: conanfile 'exports' shouldn't be a method, use 'export()' instead" in client.out


class TestExportsSourcesMethod:

    def test_export_sources_method(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import copy

            class MethodConan(ConanFile):
                exports_sources = "file.txt"
                def export_sources(self):
                    copy(self, "LICENSE.md", self.recipe_folder, self.export_sources_folder)
            """)
        client.save({"conanfile.py": conanfile, "LICENSE.md": "license", "file.txt": "file"})
        client.run("export . --name=pkg --version=0.1")
        assert "pkg/0.1: Copied 1 '.txt' file: file.txt" in client.out
        assert "Copied 1 '.md' file: LICENSE.md" in client.out

        layout = client.exported_layout()

        exported_files = os.listdir(layout.export_sources())
        assert "file.txt" in exported_files
        assert "LICENSE.md" in exported_files

    def test_export_source_folders(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.tools.files import save, load
           import os

           class MethodConan(ConanFile):
               def export_sources(self):
                   content = load(self, os.path.join(os.getcwd(), "data.txt"))
                   save(self, os.path.join(self.export_sources_folder, "myfile.txt"), content)
           """)
        client.save({"recipe/conanfile.py": conanfile, "recipe/data.txt": "mycontent"})
        client.run("export recipe --name=pkg --version=0.1")
        layout = client.exported_layout()
        assert "mycontent" == load(os.path.join(layout.export_sources(), "myfile.txt"))
        client.current_folder = os.path.join(client.current_folder, "recipe")
        client.run("export . --name=pkg --version=0.1")
        layout = client.exported_layout()
        assert "mycontent" == load(os.path.join(layout.export_sources(), "myfile.txt"))

    def test_export_sources_attribute_error(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class MethodConan(ConanFile):
                export_sources = "file.txt"
            """)
        client.save({"conanfile.py": conanfile, "file.txt": "file"})
        client.run("export . --name=pkg --version=0.1", assert_error=True)
        assert "ERROR: conanfile 'export_sources' must be a method" in client.out

    def test_exports_sources_method_error(self):
        client = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class MethodConan(ConanFile):
                def exports_sources(self):
                    pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=0.1", assert_error=True)
        assert ("ERROR: conanfile 'exports_sources' shouldn't be a method, "
                "use 'export_sources()' instead") in client.out

    def test_exports_sources_upload_error(self):
        # https://github.com/conan-io/conan/issues/7377
        client = TestClient(default_server_user=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import load, copy

            class MethodConan(ConanFile):
                def export_sources(self):
                    copy(self, "*", self.recipe_folder, self.export_sources_folder)
                def build(self):
                    self.output.info("CONTENT: %s" % load(self, "myfile.txt"))
            """)
        client.save({"conanfile.py": conanfile,
                     "myfile.txt": "mycontent"})
        client.run("export . --name=pkg --version=0.1")
        assert "Copied 1 '.txt' file: myfile.txt" in client.out
        client.run("upload pkg/0.1 -r default")
        client.run("remove * -c")
        client.run("install --requires=pkg/0.1@ --build='*'")
        assert "pkg/0.1: Sources downloaded from 'default'" in client.out
        assert "pkg/0.1: CONTENT: mycontent" in client.out
