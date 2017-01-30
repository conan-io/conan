import unittest
from conans.test.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.paths import EXPORT_SOURCES_DIR, EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME
from nose_parameterized.parameterized import parameterized
from conans.util.files import relative_dirs, load, save, md5sum
import six
from conans.model.manifest import FileTreeManifest
from collections import OrderedDict

conanfile_py = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*.h", "*.cpp"
    def package(self):
        self.copy("*.h", "include")
"""


class ExportsSourcesTest(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.other_server = TestServer()
        servers = OrderedDict([("default", self.server),
                               ("other", self.other_server)])
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")],
                                                    "other": [("lasote", "mypass")]})
        self.client = client
        self.reference = ConanFileReference.loads("Hello/0.1@lasote/testing")
        self.package_reference = PackageReference(self.reference,
                                                  "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.source_folder = self.client.client_cache.source(self.reference)
        self.package_folder = self.client.client_cache.package(self.package_reference)
        self.export_folder = self.client.client_cache.export(self.reference)
        self.export_sources_folder = os.path.join(self.export_folder, EXPORT_SOURCES_DIR)

    def _check_source_folder(self):
        """ Source folder MUST be always the same
        """
        expected_sources = sorted(['conanfile.py', 'conanmanifest.txt', "hello.h"])
        self.assertEqual(sorted(os.listdir(self.source_folder)), expected_sources)

    def _check_package_folder(self):
        """ Package folder must be always the same (might have tgz after upload)
        """
        expected_package = sorted(["conaninfo.txt", "conanmanifest.txt",
                                   os.sep.join(["include", "hello.h"])])
        self.assertEqual(sorted(relative_dirs(self.package_folder)), expected_package)

    def _check_server_folder(self, mode, server=None):
        if mode == "exports_sources":
            expected_server = sorted([EXPORT_SOURCES_TGZ_NAME, 'conanfile.py',
                                      'conanmanifest.txt'])
        if mode == "exports":
            expected_server = sorted([EXPORT_TGZ_NAME, 'conanfile.py', 'conanmanifest.txt'])
        server = server or self.server
        self.assertEqual(sorted(os.listdir(server.paths.export(self.reference))),
                         expected_server)

    def _check_export_folder(self, mode):
        if mode == "exports_sources":
            expected_exports = sorted([EXPORT_SOURCES_DIR, 'conanfile.py', 'conanmanifest.txt'])
            expected_exports_sources = ["hello.h"]
        if mode == "exports":
            expected_exports = sorted([EXPORT_SOURCES_DIR, 'conanfile.py', 'conanmanifest.txt',
                                       "hello.h"])
            expected_exports_sources = []
        # The export folder might contain or not temporary Python files
        cached = "__pycache__" if six.PY3 else "conanfile.pyc"
        exports = [f for f in os.listdir(self.export_folder) if f != cached]
        exports_sources = [f for f in os.listdir(self.export_sources_folder) if f != cached]
        self.assertEqual(sorted(exports), expected_exports)
        self.assertEqual(sorted(exports_sources), expected_exports_sources)

    def _check_export_installed_folder(self, mode, reuploaded=False, updated=False):
        """ Just installed, no EXPORT_SOURCES_DIR is present
        """
        if mode == "exports_sources":
            expected_exports = ['conanfile.py', 'conanmanifest.txt']

        if mode == "exports":
            expected_exports = ['conanfile.py', 'conanmanifest.txt', "hello.h"]
            if reuploaded:
                expected_exports.append("conan_export.tgz")
        if updated:
            expected_exports.append("license.txt")
        expected_exports = sorted(expected_exports)
        # The export folder might contain or not temporary Python files
        cached = "__pycache__" if six.PY3 else "conanfile.pyc"
        exports = [f for f in os.listdir(self.export_folder) if f != cached]
        self.assertEqual(sorted(exports), expected_exports)
        self.assertFalse(os.path.exists(self.export_sources_folder))

    def _check_export_uploaded_folder(self, mode):
        if mode == "exports_sources":
            expected_pkg_exports = sorted([EXPORT_SOURCES_DIR, 'conanfile.py',
                                           'conanmanifest.txt', EXPORT_SOURCES_TGZ_NAME])
            expected_exports_sources = ["hello.h"]
        if mode == "exports":
            expected_pkg_exports = sorted([EXPORT_SOURCES_DIR, 'conanfile.py',
                                           'conanmanifest.txt', "hello.h", EXPORT_TGZ_NAME])
            expected_exports_sources = []
        cached = "__pycache__" if six.PY3 else "conanfile.pyc"
        exports = [f for f in os.listdir(self.export_folder) if f != cached]
        exports_sources = [f for f in os.listdir(self.export_sources_folder) if f != cached]
        self.assertEqual(sorted(exports), expected_pkg_exports)
        self.assertEqual(sorted(exports_sources), expected_exports_sources)

    def _check_manifest(self, mode):
        manifest = load(os.path.join(self.client.current_folder,
                                     ".conan_manifests/Hello/0.1/lasote/testing/export/"
                                     "conanmanifest.txt"))
        if mode == "exports_sources":
            self.assertIn(".conan_export_sources/hello.h: 5d41402abc4b2a76b9719d911017c592",
                          manifest.splitlines())
        else:
            self.assertIn("hello.h: 5d41402abc4b2a76b9719d911017c592",
                          manifest.splitlines())

    @parameterized.expand([("exports", ), ("exports_sources", )])
    def export_test(self, mode):
        conanfile = conanfile_py if mode == "exports" else conanfile_py.replace("exports",
                                                                                "exports_sources")
        self.client.save({"conanfile.py": conanfile,
                          "hello.h": "hello"})

        self.client.run("export lasote/testing")
        self._check_export_folder(mode)

        # now build package
        self.client.run("install Hello/0.1@lasote/testing --build=missing")
        # Source folder and package should be exatly the same
        self._check_export_folder(mode)
        self._check_source_folder()
        self._check_package_folder()

        # upload to remote
        self.client.run("upload Hello/0.1@lasote/testing --all")
        self._check_export_uploaded_folder(mode)
        self._check_server_folder(mode)

        # remove local
        self.client.run('remove Hello/0.1@lasote/testing -f')
        self.assertFalse(os.path.exists(self.export_folder))

        # install from remote
        self.client.run("install Hello/0.1@lasote/testing")
        self.assertFalse(os.path.exists(self.source_folder))
        self._check_export_installed_folder(mode)
        self._check_package_folder()

        # Manifests must work too!
        self.client.run("install Hello/0.1@lasote/testing --manifests")
        self.assertFalse(os.path.exists(self.source_folder))
        # The manifests retrieve the normal state, as it retrieves sources
        self._check_export_folder(mode)
        self._check_package_folder()
        self._check_manifest(mode)

        # lets try to verify
        self.client.run('remove Hello/0.1@lasote/testing -f')
        self.assertFalse(os.path.exists(self.export_folder))
        self.client.run("install Hello/0.1@lasote/testing --verify")
        self.assertFalse(os.path.exists(self.source_folder))
        # The manifests retrieve the normal state, as it retrieves sources
        self._check_export_folder(mode)
        self._check_package_folder()
        self._check_manifest(mode)

    @parameterized.expand([("exports", ), ("exports_sources", )])
    def export_upload_test(self, mode):
        conanfile = conanfile_py if mode == "exports" else conanfile_py.replace("exports",
                                                                                "exports_sources")
        self.client.save({"conanfile.py": conanfile,
                          "hello.h": "hello"})

        self.client.run("export lasote/testing")

        self.client.run("upload Hello/0.1@lasote/testing")
        self.assertFalse(os.path.exists(self.source_folder))
        self._check_export_uploaded_folder(mode)
        self._check_server_folder(mode)

        # remove local
        self.client.run('remove Hello/0.1@lasote/testing -f')
        self.assertFalse(os.path.exists(self.export_folder))

        # install from remote
        self.client.run("install Hello/0.1@lasote/testing --build")
        self._check_export_folder(mode)
        self._check_source_folder()
        self._check_package_folder()

        # Manifests must work too!
        self.client.run("install Hello/0.1@lasote/testing --manifests")
        # The manifests retrieve the normal state, as it retrieves sources
        self._check_export_folder(mode)
        self._check_package_folder()
        self._check_manifest(mode)

    @parameterized.expand([("exports", ), ("exports_sources", )])
    def reupload_test(self, mode):
        """ try to reupload to same and other remote
        """
        conanfile = conanfile_py if mode == "exports" else conanfile_py.replace("exports",
                                                                                "exports_sources")
        self.client.save({"conanfile.py": conanfile,
                          "hello.h": "hello"})

        self.client.run("export lasote/testing")
        self.client.run("install Hello/0.1@lasote/testing --build=missing")
        self.client.run("upload Hello/0.1@lasote/testing --all")
        self.client.run('remove Hello/0.1@lasote/testing -f')
        self.client.run("install Hello/0.1@lasote/testing")

        # upload to remote again, the folder remains as installed
        self.client.run("upload Hello/0.1@lasote/testing --all")
        self._check_export_installed_folder(mode, reuploaded=True)
        self._check_server_folder(mode)

        self.client.run("upload Hello/0.1@lasote/testing --all -r=other")
        self._check_export_uploaded_folder(mode)
        self._check_server_folder(mode, self.other_server)

    @parameterized.expand([("exports", ), ("exports_sources", )])
    def update_test(self, mode):
        conanfile = conanfile_py if mode == "exports" else conanfile_py.replace("exports",
                                                                                "exports_sources")
        self.client.save({"conanfile.py": conanfile,
                          "hello.h": "hello"})

        self.client.run("export lasote/testing")
        self.client.run("install Hello/0.1@lasote/testing --build=missing")
        self.client.run("upload Hello/0.1@lasote/testing --all")
        self.client.run('remove Hello/0.1@lasote/testing -f')
        self.client.run("install Hello/0.1@lasote/testing")

        # upload to remote again, the folder remains as installed
        self.client.run("install Hello/0.1@lasote/testing --update")
        self.assertIn("Hello/0.1@lasote/testing: Already installed!", self.client.user_io.out)
        self._check_export_installed_folder(mode)

        server_path = self.server.paths.export(self.reference)
        save(os.path.join(server_path, "license.txt"), "mylicense")
        manifest_path = os.path.join(server_path, "conanmanifest.txt")
        manifest = FileTreeManifest.loads(load(manifest_path))
        manifest.time += 1
        manifest.file_sums["license.txt"] = md5sum(os.path.join(server_path, "license.txt"))
        save(manifest_path, str(manifest))

        self.client.run("install Hello/0.1@lasote/testing --update")
        self._check_export_installed_folder(mode, updated=True)
