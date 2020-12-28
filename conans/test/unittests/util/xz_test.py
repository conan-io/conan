import os
import tarfile
import unittest
from unittest import TestCase

import six
from six import StringIO
import pytest

from conans import DEFAULT_REVISION_V1
from conans.client.output import ConanOutput
from conans.client.tools.files import save, unzip
from conans.errors import ConanException
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer
from conans.test.utils.mocks import TestBufferConanOutput
from conans.util.files import load, save_files


class XZTest(TestCase):
    output = TestBufferConanOutput()

    def test_error_xz(self):
        server = TestServer()
        ref = ConanFileReference.loads("Pkg/0.1@user/channel")
        ref = ref.copy_with_rev(DEFAULT_REVISION_V1)
        export = server.server_store.export(ref)
        server.server_store.update_last_revision(ref)
        save_files(export, {"conanfile.py": "#",
                            "conanmanifest.txt": "#",
                            "conan_export.txz": "#"})
        client = TestClient(servers={"default": server},
                            users={"default": [("lasote", "mypass")]})
        client.run("install Pkg/0.1@user/channel", assert_error=True)
        self.assertIn("ERROR: This Conan version is not prepared to handle "
                      "'conan_export.txz' file format", client.out)

    def test_error_sources_xz(self):
        server = TestServer()
        ref = ConanFileReference.loads("Pkg/0.1@user/channel")
        ref = ref.copy_with_rev(DEFAULT_REVISION_V1)
        client = TestClient(servers={"default": server},
                            users={"default": [("lasote", "mypass")]})
        server.server_store.update_last_revision(ref)
        export = server.server_store.export(ref)
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    exports_sources = "*"
"""
        save_files(export, {"conanfile.py": conanfile,
                            "conanmanifest.txt": "1",
                            "conan_sources.txz": "#"})
        client.run("install Pkg/0.1@user/channel --build", assert_error=True)
        self.assertIn("ERROR: This Conan version is not prepared to handle "
                      "'conan_sources.txz' file format", client.out)

    def test_error_package_xz(self):
        server = TestServer()
        ref = ConanFileReference.loads("Pkg/0.1@user/channel")
        ref = ref.copy_with_rev(DEFAULT_REVISION_V1)
        client = TestClient(servers={"default": server},
                            users={"default": [("lasote", "mypass")]})
        server.server_store.update_last_revision(ref)
        export = server.server_store.export(ref)  # *1 the path can't be known before upload a revision
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    exports_sources = "*"
"""
        save_files(export, {"conanfile.py": conanfile,
                            "conanmanifest.txt": "1"})
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID, DEFAULT_REVISION_V1)
        server.server_store.update_last_package_revision(pref.copy_with_revs(DEFAULT_REVISION_V1,
                                                                             DEFAULT_REVISION_V1))

        package = server.server_store.package(pref)
        save_files(package, {"conaninfo.txt": "#",
                             "conanmanifest.txt": "1",
                             "conan_package.txz": "#"})
        client.run("install Pkg/0.1@user/channel", assert_error=True)
        self.assertIn("ERROR: This Conan version is not prepared to handle "
                      "'conan_package.txz' file format", client.out)

    @pytest.mark.skipif(not six.PY3, reason="only Py3")
    def test(self):
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "a_file.txt")
        save(file_path, "my content!")
        txz = os.path.join(tmp_dir, "sample.tar.xz")
        with tarfile.open(txz, "w:xz") as tar:
            tar.add(file_path, "a_file.txt")

        dest_folder = temp_folder()
        unzip(txz, dest_folder, output=ConanOutput(StringIO()))
        content = load(os.path.join(dest_folder, "a_file.txt"))
        self.assertEqual(content, "my content!")

    @pytest.mark.skipif(not six.PY2, reason="only Py2")
    def test_error_python2(self):
        with six.assertRaisesRegex(self, ConanException, "XZ format not supported in Python 2"):
            dest_folder = temp_folder()
            unzip("somefile.tar.xz", dest_folder, output=self.output)
