import os
import platform
import unittest

import pytest
from parameterized.parameterized import parameterized

from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE, CONAN_MANIFEST
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer
from conans.util.files import load, md5, save


def export_folder(base, ref):
    try:
        ref = ConanFileReference.loads(repr(ref))
    except Exception:
        pass
    path = ref.dir_repr() if isinstance(ref, ConanFileReference) else ref
    return os.path.abspath(os.path.join(base, path, "export"))


def package_folder(base, pref):
    return os.path.join(base, pref.ref.dir_repr(), "package", pref.id)


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
        self.ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        self.client.save(self.files)
        self.client.run("export . lasote/stable")

    @parameterized.expand([(True, ), (False, )])
    def test_test_package(self, use_abs_folder):
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
        self.assertIn("Chat/0.1@lasote/stable (test package): TEST OK", self.client.out)
        self.assertIn("Installed manifest for 'Chat/0.1@lasote/stable' from local cache",
                      self.client.out)
        self.assertIn("Installed manifest for 'Hello/0.1@lasote/stable' from local cache",
                      self.client.out)

        self.assertTrue(os.path.exists(os.path.join(export_folder(output_folder, self.ref),
                                                    CONAN_MANIFEST)))
        pref = PackageReference.loads("Hello/0.1@lasote/stable:%s" % NO_SETTINGS_PACKAGE_ID)
        self.assertTrue(os.path.exists(os.path.join(package_folder(output_folder, pref),
                                                    CONAN_MANIFEST)))
        # now verify
        self.client.run("create . lasote/stable --verify%s" % dest)
        self.assertIn("Manifest for 'Hello/0.1@lasote/stable': OK", self.client.out)
        self.assertIn("Manifest for '%s': OK" % str(pref), self.client.out)

    def _capture_verify_manifest(self, reference, remote="local cache", folder=""):
        self.client.run("install %s --build missing --manifests %s" % (str(reference), folder))
        self.assertIn("Installed manifest for 'Hello/0.1@lasote/stable' from %s" % remote,
                      self.client.out)
        self.assertIn("Installed manifest for 'Hello/0.1@lasote/stable:"
                      "%s' from %s" % (NO_SETTINGS_PACKAGE_ID, remote),
                      self.client.out)

        real_folder = folder or ".conan_manifests"
        output_folder = os.path.join(self.client.current_folder, real_folder)
        self.assertTrue(os.path.exists(os.path.join(export_folder(output_folder, self.ref),
                                                    CONAN_MANIFEST)))
        pref = PackageReference.loads("Hello/0.1@lasote/stable:%s" % NO_SETTINGS_PACKAGE_ID)
        self.assertTrue(os.path.exists(os.path.join(package_folder(output_folder, pref),
                                                    CONAN_MANIFEST)))

        # again should do nothing
        self.client.run("install %s --build missing --manifests %s"
                        % (str(self.ref), folder))
        self.assertNotIn("Installed manifest", self.client.out)

        # now verify
        self.client.run("install %s --build missing --verify %s" % (str(self.ref), folder))
        self.assertIn("Manifest for 'Hello/0.1@lasote/stable': OK", self.client.out)
        self.assertIn("Manifest for '%s': OK" % str(pref), self.client.out)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Only Windows with shortpaths")
    def test_capture_verify_short_paths_manifest(self):
        conanfile = """from conans import ConanFile

class ConanFileTest(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"
    short_paths = True
"""
        self.files = {CONANFILE: conanfile, "data.txt": "MyData"}
        self.client.save(self.files)
        self.client.run("export . lasote/stable")
        self._capture_verify_manifest("Hello/0.1@lasote/stable")

    def test_capture_verify_manifest(self):
        self._capture_verify_manifest("Hello/0.1@lasote/stable")

    def test_conanfile_capture_verify_manifest(self):
        files = {"conanfile.txt": "[requires]\nHello/0.1@lasote/stable"}
        self.client.save(files, clean_first=True)
        self._capture_verify_manifest(".")

    def test_capture_verify_manifest_folder(self):
        self._capture_verify_manifest("Hello/0.1@lasote/stable", folder="my_custom_folder")

    def test_conanfile_capture_verify_manifest_folder(self):
        files = {"conanfile.txt": "[requires]\nHello/0.1@lasote/stable"}
        self.client.save(files, clean_first=True)
        folder = "mymanifests"
        self._capture_verify_manifest(".", folder=folder)

        conanfile = """from conans import ConanFile
class ConanFileTest(ConanFile):
    name = "Hello2"
    version = "0.1"
"""
        # Do not adjust cpu_count, it is reusing a cache
        client = TestClient(cache_folder=self.client.cache_folder, cpu_count=False)
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")

        files = {"conanfile.txt": "[requires]\nHello2/0.1@lasote/stable\nHello/0.1@lasote/stable"}
        self.client.save(files)

        self.client.run("install . --build missing --manifests %s" % folder)

        remote = "local cache"
        pref = PackageReference.loads("Hello/0.1@lasote/stable:%s" % NO_SETTINGS_PACKAGE_ID)
        self.assertIn("Manifest for 'Hello/0.1@lasote/stable': OK", self.client.out)
        self.assertIn("Manifest for '%s': OK" % str(pref), self.client.out)
        self.assertIn("Installed manifest for 'Hello2/0.1@lasote/stable' from %s" % remote,
                      self.client.out)
        self.assertIn("Installed manifest for 'Hello2/0.1@lasote/stable:%s' from %s"
                      % (NO_SETTINGS_PACKAGE_ID, remote), self.client.out)

        output_folder = os.path.join(self.client.current_folder, folder)
        self.assertTrue(os.path.exists(os.path.join(export_folder(output_folder, self.ref),
                                                    CONAN_MANIFEST)))
        self.assertTrue(os.path.exists(os.path.join(package_folder(output_folder, pref),
                                                    CONAN_MANIFEST)))

    def test_remote_capture_verify_manifest(self):
        self.client.run("upload %s --all" % str(self.ref))
        self.client.run("remove Hello* -f")
        files = {"conanfile.txt": "[requires]\nHello/0.1@lasote/stable"}
        self.client.save(files, clean_first=True)
        self._capture_verify_manifest(".", remote="default")

    def _failed_verify(self, reference, remote="local cache"):
        self.client.run("install %s --build missing --manifests" % str(reference))
        self.assertIn("Installed manifest for 'Hello/0.1@lasote/stable' from %s" % remote,
                      self.client.out)
        self.assertIn("Installed manifest for 'Hello/0.1@lasote/stable:"
                      "%s' from %s" % (NO_SETTINGS_PACKAGE_ID, remote), self.client.out)

        output_folder = os.path.join(self.client.current_folder, ".conan_manifests")
        self.assertTrue(os.path.exists(os.path.join(export_folder(output_folder, self.ref),
                                                    CONAN_MANIFEST)))

        pref = PackageReference.loads("Hello/0.1@lasote/stable:%s" % NO_SETTINGS_PACKAGE_ID)
        self.assertTrue(os.path.exists(os.path.join(package_folder(output_folder, pref),
                                                    CONAN_MANIFEST)))

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
        client.run("upload %s --all" % str(self.ref))

        # now verify, with update
        self.client.run("remove Hello/0.1@lasote/stable -f")
        self.client.run("install %s --build missing --verify"
                        % str(self.ref),
                        assert_error=True)
        self.assertNotIn("Manifest for 'Hello/0.1@lasote/stable': OK", self.client.out)
        self.assertNotIn("Manifest for '%s': OK" % str(pref), self.client.out)
        self.assertIn("Modified or new manifest 'Hello/0.1@lasote/stable' detected",
                      self.client.out)

    def test_capture_verify_error_manifest(self):
        self._failed_verify("Hello/0.1@lasote/stable")

    def test_conanfile_capture_verify_error_manifest(self):
        files = {"conanfile.txt": "[requires]\nHello/0.1@lasote/stable"}
        self.client.save(files, clean_first=True)
        self._failed_verify(".")

    def _failed_package_verify(self, reference, remote="local cache"):
        self.client.run("install %s --build missing --manifests" % str(reference))
        self.assertIn("Installed manifest for 'Hello/0.1@lasote/stable' from %s" % remote,
                      self.client.out)
        self.assertIn("Installed manifest for 'Hello/0.1@lasote/stable:"
                      "%s' from %s" % (NO_SETTINGS_PACKAGE_ID, remote),
                      self.client.out)

        output_folder = os.path.join(self.client.current_folder, ".conan_manifests")
        self.assertTrue(os.path.exists(os.path.join(export_folder(output_folder, self.ref),
                                                    CONAN_MANIFEST)))

        pref = PackageReference.loads("Hello/0.1@lasote/stable: %s" % NO_SETTINGS_PACKAGE_ID)
        self.assertTrue(os.path.exists(os.path.join(package_folder(output_folder, pref),
                                                    CONAN_MANIFEST)))

        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

        client.save(self.files)
        client.run("export . lasote/stable")
        client.run("install Hello/0.1@lasote/stable --build=missing")
        package_folder_path = client.cache.package_layout(pref.ref).package(pref)
        info = os.path.join(package_folder_path, "conaninfo.txt")
        info_content = load(info)
        info_content += "# Dummy string"
        save(info, info_content)
        manifest = FileTreeManifest.load(package_folder_path)
        manifest.file_sums["conaninfo.txt"] = md5(info_content)
        manifest.save(package_folder_path)

        client.run("upload %s --all" % str(self.ref))

        # now verify, with update
        self.client.run("remove Hello/0.1@lasote/stable -f")
        self.client.run("install %s --build missing --verify"
                        % str(self.ref),
                        assert_error=True)
        self.assertNotIn("Manifest for 'Hello/0.1@lasote/stable': OK", self.client.out)
        self.assertNotIn("Manifest for '%s': OK" % str(pref), self.client.out)
        self.assertIn("Modified or new manifest '%s' detected" % str(pref),
                      self.client.out)

    def test_capture_verify_package_error_manifest(self):
        self._failed_package_verify("Hello/0.1@lasote/stable")

    def test_conanfile_capture_verify_package_error_manifest(self):
        files = {"conanfile.txt": "[requires]\nHello/0.1@lasote/stable"}
        self.client.save(files, clean_first=True)
        self._failed_package_verify(".")

    def test_manifest_wrong_folder(self):
        reference = "Hello/0.1@lasote/stable"
        self.client.run("install %s --build missing --verify whatever"
                        % str(reference), assert_error=True)
        self.assertIn("Manifest folder does not exist:", self.client.out)

    def test_manifest_wrong_args(self):
        reference = "Hello/0.1@lasote/stable"
        self.client.run("install %s --build missing --verify -m"
                        % str(reference), assert_error=True)
        self.assertIn("ERROR: Do not specify both", self.client.out)
        self.client.run("install %s --build missing -mi -m"
                        % str(reference), assert_error=True)
        self.assertIn("ERROR: Do not specify both", self.client.out)

    def test_corrupted_recipe(self):
        export_path = self.client.cache.package_layout(self.ref).export()
        file_path = os.path.join(export_path, "data.txt")
        save(file_path, "BAD CONTENT")

        self.client.run("install %s --build missing --manifests" % str(self.ref),
                        assert_error=True)
        self.assertIn("Hello/0.1@lasote/stable local cache package is corrupted",
                      self.client.out)

    def test_corrupted_package(self):
        self.client.run("install %s --build missing" % str(self.ref))
        pref = PackageReference.loads("Hello/0.1@lasote/stable:%s" % NO_SETTINGS_PACKAGE_ID)
        package_path = self.client.cache.package_layout(pref.ref).package(pref)
        file_path = os.path.join(package_path, "conaninfo.txt")
        save(file_path, load(file_path) + "  ")

        self.client.run("install %s --build missing --manifests" % str(self.ref),
                        assert_error=True)
        self.assertIn("%s local cache package is corrupted" % str(pref),
                      self.client.out)
