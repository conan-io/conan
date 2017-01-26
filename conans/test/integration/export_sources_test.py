import unittest
from conans.test.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.paths import EXPORT_SOURCES_DIR, EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME
from nose_parameterized.parameterized import parameterized
from conans.util.files import relative_dirs

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

    @parameterized.expand([("exports", ), ("exports_sources", )])
    def export_test(self, mode):
        server = TestServer()
        servers = {"default": server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        if mode == "exports_sources":
            conanfile = conanfile_py.replace("exports", "exports_sources")
            expected_exports = sorted([EXPORT_SOURCES_DIR, 'conanfile.py', 'conanmanifest.txt'])
            expected_exports_sources = ["hello.h"]
            expected_pkg_exports = sorted([EXPORT_SOURCES_DIR, 'conanfile.py', 'conanfile.pyc',
                                           'conanmanifest.txt', EXPORT_SOURCES_TGZ_NAME])
            expected_install_exports = sorted(['conanfile.py', 'conanfile.pyc', 'conanmanifest.txt'])
            expected_server = sorted([EXPORT_SOURCES_TGZ_NAME, 'conanfile.py', 'conanmanifest.txt'])
        if mode == "exports":
            conanfile = conanfile_py
            expected_exports = sorted([EXPORT_SOURCES_DIR, 'conanfile.py', 'conanmanifest.txt',
                                       "hello.h"])
            expected_exports_sources = []
            expected_pkg_exports = sorted([EXPORT_SOURCES_DIR, 'conanfile.py', 'conanfile.pyc',
                                           'conanmanifest.txt', "hello.h", EXPORT_TGZ_NAME])
            expected_install_exports = sorted(['conanfile.py', 'conanfile.pyc',
                                               'conanmanifest.txt', 'hello.h'])
            expected_server = sorted([EXPORT_TGZ_NAME, 'conanfile.py', 'conanmanifest.txt'])
        expected_sources = sorted(['conanfile.py', 'conanfile.pyc', 'conanmanifest.txt', "hello.h"])
        expected_package = sorted(["conaninfo.txt", "conanmanifest.txt",
                                   os.sep.join(["include", "hello.h"])])

        client.save({"conanfile.py": conanfile,
                     "hello.h": "hello"})

        # definition of folders
        ref = ConanFileReference.loads("Hello/0.1@lasote/testing")
        export = client.client_cache.export(ref)
        export_sources = os.path.join(export, EXPORT_SOURCES_DIR)
        source_folder = client.client_cache.source(ref)
        package_ref = PackageReference(ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = client.client_cache.package(package_ref)

        client.run("export lasote/testing")
        self.assertEqual(sorted(os.listdir(export)), expected_exports)
        self.assertEqual(sorted(os.listdir(export_sources)), expected_exports_sources)

        # now build package
        client.run("install Hello/0.1@lasote/testing --build=missing")
        # Source folder and package should be exatly the same
        self.assertEqual(sorted(os.listdir(source_folder)), expected_sources)
        self.assertEqual(sorted(relative_dirs(package_folder)), expected_package)

        # upload to remote
        client.run("upload Hello/0.1@lasote/testing --all")
        self.assertEqual(sorted(os.listdir(export)), expected_pkg_exports)
        self.assertEqual(sorted(os.listdir(export_sources)), expected_exports_sources)
        self.assertEqual(sorted(os.listdir(server.paths.export(ref))), expected_server)

        # remove local
        client.run('remove Hello/0.1@lasote/testing -f')
        self.assertFalse(os.path.exists(export))

        # install from remote
        client.run("install Hello/0.1@lasote/testing")
        self.assertEqual(sorted(os.listdir(export)), expected_install_exports)
        self.assertEqual(sorted(relative_dirs(package_folder)), expected_package)
