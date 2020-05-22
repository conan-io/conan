import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


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
        self.assertIn("pkg/0.1 exports: Copied 1 '.txt' file: file.txt", client.out)
        self.assertIn("pkg/0.1 export() method: Copied 1 '.md' file: LICENSE.md", client.out)

        layout = client.cache.package_layout(ConanFileReference.loads("pkg/0.1"))
        exported_files = os.listdir(layout.export())
        self.assertIn("file.txt", exported_files)
        self.assertIn("LICENSE.md", exported_files)

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
