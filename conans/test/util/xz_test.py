import os
from unittest import TestCase
import six
import unittest
import tarfile

from conans.test.utils.test_files import temp_folder
from conans.tools import unzip, save
from conans.util.files import load, save_files
from conans.errors import ConanException
from conans.test.utils.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference, PackageReference


class XZTest(TestCase):
    def test_error_xz(self):
        server = TestServer()
        ref = ConanFileReference.loads("Pkg/0.1@user/channel")
        export = server.paths.export(ref)
        save_files(export, {"conanfile.py": "#",
                            "conanmanifest.txt": "#",
                            "conan_export.txz": "#"})
        client = TestClient(servers={"default": server},
                            users={"default": [("lasote", "mypass")]})
        error = client.run("install Pkg/0.1@user/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: This Conan version is not prepared to handle "
                      "'conan_export.txz' file format", client.out)

    def test_error_sources_xz(self):
        server = TestServer()
        ref = ConanFileReference.loads("Pkg/0.1@user/channel")
        client = TestClient(servers={"default": server},
                            users={"default": [("lasote", "mypass")]})
        export = server.paths.export(ref)
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    exports_sources = "*"
"""
        save_files(export, {"conanfile.py": conanfile,
                            "conanmanifest.txt": "1",
                            "conan_sources.txz": "#"})
        error = client.run("install Pkg/0.1@user/channel --build", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: This Conan version is not prepared to handle "
                      "'conan_sources.txz' file format", client.out)

    def test_error_package_xz(self):
        server = TestServer()
        ref = ConanFileReference.loads("Pkg/0.1@user/channel")
        client = TestClient(servers={"default": server},
                            users={"default": [("lasote", "mypass")]})
        export = server.paths.export(ref)
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    exports_sources = "*"
"""
        save_files(export, {"conanfile.py": conanfile,
                            "conanmanifest.txt": "1"})
        pkg_ref = PackageReference(ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package = server.paths.package(pkg_ref)
        save_files(package, {"conaninfo.txt": "#",
                             "conanmanifest.txt": "1",
                             "conan_package.txz": "#"})
        error = client.run("install Pkg/0.1@user/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: This Conan version is not prepared to handle "
                      "'conan_package.txz' file format", client.out)

    @unittest.skipUnless(six.PY3, "only Py3")
    def test(self):
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "a_file.txt")
        save(file_path, "my content!")
        txz = os.path.join(tmp_dir, "sample.tar.xz")
        with tarfile.open(txz, "w:xz") as tar:
            tar.add(file_path, "a_file.txt")

        dest_folder = temp_folder()
        unzip(txz, dest_folder)
        content = load(os.path.join(dest_folder, "a_file.txt"))
        self.assertEqual(content, "my content!")

    @unittest.skipUnless(six.PY2, "only Py2")
    def test_error_python2(self):
        with self.assertRaisesRegexp(ConanException, "XZ format not supported in Python 2"):
            dest_folder = temp_folder()
            unzip("somefile.tar.xz", dest_folder)
