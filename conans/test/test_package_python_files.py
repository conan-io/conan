import os
import textwrap
import unittest

from conans.util.files import load
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


class TestPackagePythonFiles(unittest.TestCase):
    def test_package_python_files(self):
        client = TestClient(default_server_user=True)
        client.run("config set general.keep_python_files=True")
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                exports_sources = "*"
                def package(self):
                    self.copy("*")
            """)
        client.save({"conanfile.py": conanfile,
                     "myfile.pyc": "",
                     "myfile.pyo": "",
                     ".DS_Store": ""})
        client.run("create . pkg/0.1@")
        ref = ConanFileReference.loads("pkg/0.1")
        layout = client.cache.package_layout(ref)
        export = layout.export()
        export_sources = layout.export_sources()
        self.assertTrue(os.path.isfile(os.path.join(export_sources, "myfile.pyc")))
        self.assertTrue(os.path.isfile(os.path.join(export_sources, "myfile.pyo")))
        self.assertTrue(os.path.isfile(os.path.join(export_sources, ".DS_Store")))
        manifest = load(os.path.join(export, "conanmanifest.txt"))
        self.assertIn("myfile.pyc", manifest)
        self.assertIn("myfile.pyo", manifest)
        self.assertNotIn(".DS_Store", manifest)
        pkg_folder = layout.package(PackageReference(ref, NO_SETTINGS_PACKAGE_ID))
        self.assertTrue(os.path.isfile(os.path.join(pkg_folder, "myfile.pyc")))
        self.assertTrue(os.path.isfile(os.path.join(pkg_folder, "myfile.pyo")))
        self.assertTrue(os.path.isfile(os.path.join(pkg_folder, ".DS_Store")))
        manifest = load(os.path.join(pkg_folder, "conanmanifest.txt"))
        self.assertIn("myfile.pyc", manifest)
        self.assertIn("myfile.pyo", manifest)
        self.assertNotIn(".DS_Store", manifest)

        client.run("upload * --all -r=default --confirm")
        client.run("remove * -f")
        client.run("download pkg/0.1@")

        self.assertTrue(os.path.isfile(os.path.join(export_sources, "myfile.pyc")))
        self.assertTrue(os.path.isfile(os.path.join(export_sources, "myfile.pyo")))
        self.assertFalse(os.path.isfile(os.path.join(export_sources, ".DS_Store")))
        manifest = load(os.path.join(export, "conanmanifest.txt"))
        self.assertIn("myfile.pyc", manifest)
        self.assertIn("myfile.pyo", manifest)
        self.assertNotIn(".DS_Store", manifest)
        self.assertTrue(os.path.isfile(os.path.join(pkg_folder, "myfile.pyc")))
        self.assertTrue(os.path.isfile(os.path.join(pkg_folder, "myfile.pyo")))
        self.assertFalse(os.path.isfile(os.path.join(pkg_folder, ".DS_Store")))
        manifest = load(os.path.join(pkg_folder, "conanmanifest.txt"))
        self.assertIn("myfile.pyc", manifest)
        self.assertIn("myfile.pyo", manifest)
        self.assertNotIn(".DS_Store", manifest)
