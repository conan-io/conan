import os
import unittest
from parameterized.parameterized import parameterized

from conans.test.utils.tools import TestServer, TestClient
from conans.model.ref import ConanFileReference
from conans.util.files import save, load, md5
from conans.model.ref import PackageReference
from conans.paths import CONANFILE, SimplePaths, CONAN_MANIFEST
from conans.test.utils.test_files import temp_folder
from conans.model.manifest import FileTreeManifest


class ManifestValidationTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

        conanfile = """from conans import ConanFile

class ConanFileTest(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"
"""
        self.files = {CONANFILE: conanfile, "data.txt": "MyData"}
        self.reference = ConanFileReference.loads("Hello/0.1@lasote/stable")
        self.client.save(self.files)
        self.client.run("export . lasote/stable")

    @parameterized.expand([(True, ), (False, )])
    def test_package_test(self, use_abs_folder):
        self.client.run("install Hello/0.1@lasote/stable --build missing")
        conanfile = """from conans import ConanFile

class ConsumerFileTest(ConanFile):
    name = "Chat"
    version = "0.1"
    requires = "Hello/0.1@lasote/stable"
    def package_info(self):
        self.cpp_info.libs = ["MyLib"]
"""
        test_conanfile = """from conans import ConanFile

class ConsumerFileTest(ConanFile):
    requires = "Chat/0.1@lasote/stable"
    def build(self):
        self.output.info("LIBS = %s" % self.deps_cpp_info.libs[0])
    def test(self):
        self.output.info("TEST OK")
"""
        if use_abs_folder:
            output_folder = temp_folder()
            dest = '="%s"' % output_folder
        else:
            dest = ""
            output_folder = os.path.join(self.client.current_folder, ".conan_manifests")

        self.client.save({"conanfile.py": conanfile,
                          "test_package/conanfile.py": test_conanfile}, clean_first=True)

        self.client.run("create . lasote/stable --manifests%s" % dest)
        self.assertIn("Chat/0.1@lasote/stable (test package): LIBS = MyLib", self.client.out)
        self.assertIn("Chat/0.1@lasote/stable (test package): TEST OK", self.client.user_io.out)
        self.assertIn("Installed manifest for 'Chat/0.1@lasote/stable' from local cache",
                      self.client.user_io.out)
        self.assertIn("Installed manifest for 'Hello/0.1@lasote/stable' from local cache",
                      self.client.user_io.out)

        paths = SimplePaths(output_folder)
        self.assertTrue(os.path.exists(os.path.join(paths.export(self.reference), CONAN_MANIFEST)))
        package_reference = PackageReference.loads("Hello/0.1@lasote/stable:"
                                                   "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertTrue(os.path.exists(os.path.join(paths.package(package_reference), CONAN_MANIFEST)))
        # now verify
        self.client.run("create . lasote/stable --verify%s" % dest)
        self.assertIn("Manifest for 'Hello/0.1@lasote/stable': OK", self.client.user_io.out)
        self.assertIn("Manifest for '%s': OK" % str(package_reference), self.client.user_io.out)

    def _capture_verify_manifest(self, reference, remote="local cache", folder=""):
        self.client.run("install %s --build missing --manifests %s" % (str(reference), folder))
        self.assertIn("Installed manifest for 'Hello/0.1@lasote/stable' from %s" % remote,
                      self.client.user_io.out)
        self.assertIn("Installed manifest for 'Hello/0.1@lasote/stable:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9' from %s" % remote,
                      self.client.user_io.out)

        real_folder = folder or ".conan_manifests"
        output_folder = os.path.join(self.client.current_folder, real_folder)
        paths = SimplePaths(output_folder)
        self.assertTrue(os.path.exists(os.path.join(paths.export(self.reference), CONAN_MANIFEST)))
        package_reference = PackageReference.loads("Hello/0.1@lasote/stable:"
                                                   "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertTrue(os.path.exists(os.path.join(paths.package(package_reference), CONAN_MANIFEST)))

        # again should do nothing
        self.client.run("install %s --build missing --manifests %s"
                        % (str(self.reference), folder))
        self.assertNotIn("Installed manifest", self.client.user_io.out)

        # now verify
        self.client.run("install %s --build missing --verify %s" % (str(self.reference), folder))
        self.assertIn("Manifest for 'Hello/0.1@lasote/stable': OK", self.client.user_io.out)
        self.assertIn("Manifest for '%s': OK" % str(package_reference), self.client.user_io.out)

    def capture_verify_manifest_test(self):
        self._capture_verify_manifest("Hello/0.1@lasote/stable")

    def conanfile_capture_verify_manifest_test(self):
        files = {"conanfile.txt": "[requires]\nHello/0.1@lasote/stable"}
        self.client.save(files, clean_first=True)
        self._capture_verify_manifest(".")

    def capture_verify_manifest_folder_test(self):
        self._capture_verify_manifest("Hello/0.1@lasote/stable", folder="my_custom_folder")

    def conanfile_capture_verify_manifest_folder_test(self):
        files = {"conanfile.txt": "[requires]\nHello/0.1@lasote/stable"}
        self.client.save(files, clean_first=True)
        folder = "mymanifests"
        self._capture_verify_manifest(".", folder=folder)

        conanfile = """from conans import ConanFile
class ConanFileTest(ConanFile):
    name = "Hello2"
    version = "0.1"
"""
        client = TestClient(base_folder=self.client.base_folder)
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")

        files = {"conanfile.txt": "[requires]\nHello2/0.1@lasote/stable\nHello/0.1@lasote/stable"}
        self.client.save(files)

        self.client.run("install . --build missing --manifests %s" % folder)

        remote = "local cache"
        package_reference = PackageReference.loads("Hello/0.1@lasote/stable:"
                                                   "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertIn("Manifest for 'Hello/0.1@lasote/stable': OK", self.client.user_io.out)
        self.assertIn("Manifest for '%s': OK" % str(package_reference), self.client.user_io.out)
        self.assertIn("Installed manifest for 'Hello2/0.1@lasote/stable' from %s" % remote,
                      self.client.user_io.out)
        self.assertIn("Installed manifest for 'Hello2/0.1@lasote/stable:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9' from %s" % remote,
                      self.client.user_io.out)

        output_folder = os.path.join(self.client.current_folder, folder)
        paths = SimplePaths(output_folder)
        self.assertTrue(os.path.exists(os.path.join(paths.export(self.reference), CONAN_MANIFEST)))
        self.assertTrue(os.path.exists(os.path.join(paths.package(package_reference), CONAN_MANIFEST)))

    def remote_capture_verify_manifest_test(self):
        self.client.run("upload %s --all" % str(self.reference))
        self.client.run("remove Hello* -f")
        files = {"conanfile.txt": "[requires]\nHello/0.1@lasote/stable"}
        self.client.save(files, clean_first=True)
        self._capture_verify_manifest(".", remote="default")

    def _failed_verify(self, reference, remote="local cache"):
        self.client.run("install %s --build missing --manifests" % str(reference))
        self.assertIn("Installed manifest for 'Hello/0.1@lasote/stable' from %s" % remote,
                      self.client.user_io.out)
        self.assertIn("Installed manifest for 'Hello/0.1@lasote/stable:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9' from %s" % remote,
                      self.client.user_io.out)

        output_folder = os.path.join(self.client.current_folder, ".conan_manifests")
        paths = SimplePaths(output_folder)
        self.assertTrue(os.path.exists(os.path.join(paths.export(self.reference), CONAN_MANIFEST)))

        package_reference = PackageReference.loads("Hello/0.1@lasote/stable:"
                                                   "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertTrue(os.path.exists(os.path.join(paths.package(package_reference), CONAN_MANIFEST)))

        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class ConanFileTest(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"
"""
        files = {CONANFILE: conanfile, "data.txt": "MyDataHacked"}
        # Export and upload the conanfile
        client.save(files)
        client.run("export . lasote/stable")
        client.run("upload %s --all" % str(self.reference))

        # now verify, with update
        self.client.run("remove Hello/0.1@lasote/stable -f")
        self.client.run("install %s --build missing --verify"
                        % str(self.reference),
                        ignore_error=True)
        self.assertNotIn("Manifest for 'Hello/0.1@lasote/stable': OK", self.client.user_io.out)
        self.assertNotIn("Manifest for '%s': OK" % str(package_reference), self.client.user_io.out)
        self.assertIn("Modified or new manifest 'Hello/0.1@lasote/stable' detected",
                      self.client.user_io.out)

    def capture_verify_error_manifest_test(self):
        self._failed_verify("Hello/0.1@lasote/stable")

    def conanfile_capture_verify_error_manifest_test(self):
        files = {"conanfile.txt": "[requires]\nHello/0.1@lasote/stable"}
        self.client.save(files, clean_first=True)
        self._failed_verify(".")

    def _failed_package_verify(self, reference, remote="local cache"):
        self.client.run("install %s --build missing --manifests" % str(reference))
        self.assertIn("Installed manifest for 'Hello/0.1@lasote/stable' from %s" % remote,
                      self.client.user_io.out)
        self.assertIn("Installed manifest for 'Hello/0.1@lasote/stable:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9' from %s" % remote,
                      self.client.user_io.out)

        output_folder = os.path.join(self.client.current_folder, ".conan_manifests")
        paths = SimplePaths(output_folder)
        self.assertTrue(os.path.exists(os.path.join(paths.export(self.reference), CONAN_MANIFEST)))

        package_reference = PackageReference.loads("Hello/0.1@lasote/stable:"
                                                   "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertTrue(os.path.exists(os.path.join(paths.package(package_reference), CONAN_MANIFEST)))

        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

        client.save(self.files)
        client.run("export . lasote/stable")
        client.run("install Hello/0.1@lasote/stable --build=missing")
        info = os.path.join(client.paths.package(package_reference), "conaninfo.txt")
        info_content = load(info)
        info_content += "# Dummy string"
        save(info, info_content)
        package_folder = client.paths.package(package_reference)
        manifest = FileTreeManifest.load(package_folder)
        manifest.file_sums["conaninfo.txt"] = md5(info_content)
        manifest.save(package_folder)

        client.run("upload %s --all" % str(self.reference))

        # now verify, with update
        self.client.run("remove Hello/0.1@lasote/stable -f")
        self.client.run("install %s --build missing --verify"
                        % str(self.reference),
                        ignore_error=True)
        self.assertNotIn("Manifest for 'Hello/0.1@lasote/stable': OK", self.client.user_io.out)
        self.assertNotIn("Manifest for '%s': OK" % str(package_reference), self.client.user_io.out)
        self.assertIn("Modified or new manifest '%s' detected" % str(package_reference),
                      self.client.user_io.out)

    def capture_verify_package_error_manifest_test(self):
        self._failed_package_verify("Hello/0.1@lasote/stable")

    def conanfile_capture_verify_package_error_manifest_test(self):
        files = {"conanfile.txt": "[requires]\nHello/0.1@lasote/stable"}
        self.client.save(files, clean_first=True)
        self._failed_package_verify(".")

    def manifest_wrong_folder_test(self):
        reference = "Hello/0.1@lasote/stable"
        self.client.run("install %s --build missing --verify whatever"
                        % str(reference), ignore_error=True)
        self.assertIn("Manifest folder does not exist:", self.client.user_io.out)

    def manifest_wrong_args_test(self):
        reference = "Hello/0.1@lasote/stable"
        self.client.run("install %s --build missing --verify -m"
                        % str(reference), ignore_error=True)
        self.assertIn("ERROR: Do not specify both", self.client.user_io.out)
        self.client.run("install %s --build missing -mi -m"
                        % str(reference), ignore_error=True)
        self.assertIn("ERROR: Do not specify both", self.client.user_io.out)

    def test_corrupted_recipe(self):
        export_path = self.client.paths.export(self.reference)
        file_path = os.path.join(export_path, "data.txt")
        save(file_path, "BAD CONTENT")

        self.client.run("install %s --build missing --manifests" % str(self.reference),
                        ignore_error=True)
        self.assertIn("Hello/0.1@lasote/stable local cache package is corrupted",
                      self.client.user_io.out)

    def test_corrupted_package(self):
        self.client.run("install %s --build missing" % str(self.reference))
        package_reference = PackageReference.loads("Hello/0.1@lasote/stable:"
                                                   "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_path = self.client.paths.package(package_reference)
        file_path = os.path.join(package_path, "conaninfo.txt")
        save(file_path, load(file_path) + "  ")

        self.client.run("install %s --build missing --manifests" % str(self.reference),
                        ignore_error=True)
        self.assertIn("%s local cache package is corrupted" % str(package_reference),
                      self.client.user_io.out)
