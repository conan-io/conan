import unittest
from conans.test.tools import TestClient, TestServer
from conans.test.utils.test_files import hello_source_files, temp_folder
from conans.client.manager import CONANFILE
import os
from conans.paths import CONAN_MANIFEST, EXPORT_TGZ_NAME
import platform
import stat
from conans.util.files import save
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.manifest import FileTreeManifest
from conans.test.utils.test_files import uncompress_packaged_files
from conans.tools import untargz


myconan1 = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2.1"
"""


class UploadTest(unittest.TestCase):

    def setUp(self):
        servers = {}
        # All can write (for avoid authentication until we mock user_io)
        self.test_server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                      users={"lasote": "mypass"})
        servers["default"] = self.test_server
        conan_digest = FileTreeManifest('123123123', {})

        self.client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        self.conan_ref = ConanFileReference.loads("Hello/1.2.1@frodo/stable")
        reg_folder = self.client.paths.export(self.conan_ref)

        self.client.run('upload %s' % str(self.conan_ref))
        self.assertIn("There is no local conanfile exported as %s" % str(self.conan_ref),
                      self.client.user_io.out)

        files = hello_source_files()
        self.client.save(files, path=reg_folder)
        self.client.save({CONANFILE: myconan1,
                          CONAN_MANIFEST: str(conan_digest),
                          "include/math/lib1.h": "//copy",
                          "my_lib/debug/libd.a": "//copy",
                          "my_data/readme.txt": "//copy",
                          "my_bin/executable": "//copy"}, path=reg_folder)

        self.package_ref = PackageReference(self.conan_ref, "myfakeid")
        self.server_pack_folder = self.test_server.paths.package(self.package_ref)

        package_folder = self.client.paths.package(self.package_ref)
        save(os.path.join(package_folder, "include", "lib1.h"), "//header")
        save(os.path.join(package_folder, "lib", "my_lib", "libd.a"), "//lib")
        save(os.path.join(package_folder, "res", "shares", "readme.txt"),
             "//res")
        save(os.path.join(package_folder, "bin", "my_bin", "executable"), "//bin")
        os.chmod(os.path.join(package_folder, "bin", "my_bin", "executable"),
                 os.stat(os.path.join(package_folder, "bin", "my_bin", "executable")).st_mode |
                 stat.S_IRWXU)

        self.server_reg_folder = self.test_server.paths.export(self.conan_ref)
        self.assertFalse(os.path.exists(self.server_reg_folder))
        self.assertFalse(os.path.exists(self.server_pack_folder))

    def simple_test(self):
        """ basic installation of a new conans
        """

        # Try to upload an package without upload conans first
        self.client.run('upload %s -p %s' % (self.conan_ref, str(self.package_ref.package_id)),
                        ignore_error=True)
        self.assertIn("There are no remote conanfiles like %s" % str(self.conan_ref),
                      self.client.user_io.out)

        # Upload conans
        self.client.run('upload %s' % str(self.conan_ref))
        self.assertTrue(os.path.exists(self.server_reg_folder))
        self.assertFalse(os.path.exists(self.server_pack_folder))
        # Upload package
        self.client.run('upload %s -p %s'
                        % (str(self.conan_ref), str(self.package_ref.package_id)))
        self.assertTrue(os.path.exists(self.server_reg_folder))
        self.assertTrue(os.path.exists(self.server_pack_folder))

        # Test the file in the downloaded conans
        files = ['CMakeLists.txt',
                 'my_lib/debug/libd.a',
                 'hello.cpp',
                 'hello0.h',
                 CONANFILE,
                 CONAN_MANIFEST,
                 'main.cpp',
                 'include/math/lib1.h',
                 'my_data/readme.txt',
                 'my_bin/executable']

        self.assertTrue(os.path.exists(os.path.join(self.server_reg_folder, CONANFILE)))
        self.assertTrue(os.path.exists(os.path.join(self.server_reg_folder, EXPORT_TGZ_NAME)))
        tmp = temp_folder()
        untargz(os.path.join(self.server_reg_folder, EXPORT_TGZ_NAME), tmp)
        for f in files:
            if f not in (CONANFILE, CONAN_MANIFEST):
                self.assertTrue(os.path.exists(os.path.join(tmp, f)))
            else:
                self.assertFalse(os.path.exists(os.path.join(tmp, f)))

        folder = uncompress_packaged_files(self.test_server.paths, self.package_ref)

        self.assertTrue(os.path.exists(os.path.join(folder,
                                                    "include",
                                                    "lib1.h")))
        self.assertTrue(os.path.exists(os.path.join(folder,
                                                    "lib",
                                                    "my_lib/libd.a")))
        self.assertTrue(os.path.exists(os.path.join(folder,
                                                    "res",
                                                    "shares/readme.txt")))

        if platform.system() != "Windows":
            self.assertEqual(os.stat(os.path.join(folder,
                                                  "bin",
                                                  "my_bin/executable")).st_mode &
                             stat.S_IRWXU, stat.S_IRWXU)

    def upload_all_test(self):
        '''Upload conans and package together'''
        # Try to upload all conans and packages
        self.client.run('upload %s --all' % str(self.conan_ref))
        self.assertTrue(os.path.exists(self.server_reg_folder))
        self.assertTrue(os.path.exists(self.server_pack_folder))

    def force_test(self):
        '''Tries to upload a conans exported after than remote version.'''
        # Upload all conans and packages
        self.client.run('upload %s --all' % str(self.conan_ref))
        self.assertTrue(os.path.exists(self.server_reg_folder))
        self.assertTrue(os.path.exists(self.server_pack_folder))

        # Fake datetime from exported date and upload again
        digest_path = os.path.join(self.client.paths.export(self.conan_ref), CONAN_MANIFEST)
        old_digest = self.client.paths.load_digest(self.conan_ref)
        fake_digest = FileTreeManifest(2, old_digest.file_sums)
        save(digest_path, str(fake_digest))

        self.client.run('upload %s' % str(self.conan_ref), ignore_error=True)
        self.assertIn("Remote conans is newer than local conans", self.client.user_io.out)

        self.client.run('upload %s --force' % str(self.conan_ref))
        self.assertIn("Uploading %s" % str(self.conan_ref),
                      self.client.user_io.out)
