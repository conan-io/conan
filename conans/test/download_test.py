import os
import unittest

from conans.client.manager import CONANFILE
from conans.client.proxy import ConanProxy
from conans.errors import NotFoundException, ConanException
from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONAN_MANIFEST, CONANINFO
from conans.test.utils.test_files import hello_source_files
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import save


myconan1 = """
from conans import ConanFile
import platform

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2.1"
"""


class DownloadTest(unittest.TestCase):

    def test_returns_on_failures(self):
        test_server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")])
        servers = {"default": test_server}

        class Response(object):
            ok = None
            status_code = None
            charset = None
            text = ""
            headers = {}

            def __init__(self, ok, status_code):
                self.ok = ok
                self.status_code = status_code

        class BuggyRequester(object):

            def __init__(self, *args, **kwargs):
                pass

            def get(self, *args, **kwargs):
                return Response(False, 404)

        client2 = TestClient(servers=servers, requester_class=BuggyRequester)
        conan_ref = ConanFileReference.loads("Hello/1.2.1@frodo/stable")
        package_ref = PackageReference(conan_ref, "123123123")
        installer = ConanProxy(client2.paths, client2.user_io, client2.remote_manager, "default")

        with self.assertRaises(NotFoundException):
            installer.get_recipe(conan_ref)

        self.assertFalse(installer.package_available(package_ref, False, True))

        class BuggyRequester2(BuggyRequester):
            def get(self, *args, **kwargs):
                return Response(False, 500)

        client2 = TestClient(servers=servers, requester_class=BuggyRequester2)
        installer = ConanProxy(client2.paths, client2.user_io, client2.remote_manager, "default")

        try:
            installer.get_recipe(conan_ref)
        except NotFoundException:
            self.assertFalse(True)  # Shouldn't capture here
        except ConanException:
            pass

        try:
            installer.package_available(package_ref, False, True)
        except NotFoundException:
            self.assertFalse(True)  # Shouldn't capture here
        except ConanException:
            pass

    def complete_test(self):
        """ basic installation of a new conans
        """
        servers = {}
        # All can write (for avoid authentication until we mock user_io)
        test_server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")])
        servers["default"] = test_server

        conan_digest = FileTreeManifest(123123123, {})

        client = TestClient(servers=servers)
        client.init_dynamic_vars()
        conan_ref = ConanFileReference.loads("Hello/1.2.1@frodo/stable")
        reg_folder = client.paths.export(conan_ref)

        files = hello_source_files()
        client.save(files, path=reg_folder)
        client.save({CONANFILE: myconan1,
                     CONAN_MANIFEST: str(conan_digest),
                     "include/math/lib1.h": "//copy",
                     "my_lib/debug/libd.a": "//copy",
                     "my_data/readme.txt": "//copy"}, path=reg_folder)
        exports_sources_dir = client.paths.export_sources(conan_ref)
        os.makedirs(exports_sources_dir)

        package_ref = PackageReference(conan_ref, "fakeid")
        package_folder = client.paths.package(package_ref)
        save(os.path.join(package_folder, CONANINFO), "info")
        save(os.path.join(package_folder, CONAN_MANIFEST), "manifest")
        save(os.path.join(package_folder, "include", "lib1.h"), "//header")
        save(os.path.join(package_folder, "lib", "my_lib", "libd.a"), "//lib")
        save(os.path.join(package_folder, "res", "shares", "readme.txt"),
             "//res")

        digest_path = client.client_cache.digestfile_package(package_ref)
        expected_manifest = FileTreeManifest.create(os.path.dirname(digest_path))
        save(os.path.join(package_folder, CONAN_MANIFEST), str(expected_manifest))

        client.run("upload %s" % str(conan_ref))
        client.run("upload %s -p %s" % (str(conan_ref), package_ref.package_id))

        client2 = TestClient(servers=servers)
        client2.init_dynamic_vars()

        installer = ConanProxy(client2.paths, client2.user_io, client2.remote_manager, "default")

        installer.get_recipe(conan_ref)
        installer.get_package(package_ref, short_paths=False)
        # Check that the output is done in order
        lines = [line.strip() for line in str(client2.user_io.out).splitlines()
                 if line.startswith("Downloading")]
        self.assertEqual(lines, ["Downloading conanmanifest.txt",
                                 "Downloading conanfile.py",
                                 "Downloading conan_export.tgz",
                                 "Downloading conanmanifest.txt",
                                 "Downloading conaninfo.txt",
                                 "Downloading conan_package.tgz"
                                 ])

        reg_path = client2.paths.export(ConanFileReference.loads("Hello/1.2.1/frodo/stable"))
        pack_folder = client2.paths.package(package_ref)

        # Test the file in the downloaded conans
        files = ['CMakeLists.txt',
                 'my_lib/debug/libd.a',
                 'hello.cpp',
                 'hello0.h',
                 CONANFILE,
                 CONAN_MANIFEST,
                 'main.cpp',
                 'include/math/lib1.h',
                 'my_data/readme.txt']

        for _file in files:
            self.assertTrue(os.path.exists(os.path.join(reg_path, _file)))
        self.assertTrue(os.path.exists(pack_folder))

        # Test the file in the downloaded package
        self.assertTrue(os.path.exists(pack_folder))
        self.assertTrue(os.path.exists(os.path.join(pack_folder, "include",
                                                    "lib1.h")))
        self.assertTrue(os.path.exists(os.path.join(pack_folder, "lib",
                                                    "my_lib/libd.a")))
        self.assertTrue(os.path.exists(os.path.join(pack_folder, "res",
                                                    "shares/readme.txt")))
