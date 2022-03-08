import os
import tarfile
from unittest import TestCase

from conan.tools.files import unzip
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer
from conans.util.files import load, save_files, save


class XZTest(TestCase):

    def test_error_xz(self):
        server = TestServer()
        ref = RecipeReference.loads("pkg/0.1@user/channel")
        ref.revision = "myreciperev"
        export = server.server_store.export(ref)
        server.server_store.update_last_revision(ref)
        save_files(export, {"conanfile.py": str(GenConanfile()),
                            "conanmanifest.txt": "#",
                            "conan_export.txz": "#"})
        client = TestClient(servers={"default": server})
        client.run("install --requires=pkg/0.1@user/channel", assert_error=True)
        self.assertIn("This Conan version is not prepared to handle "
                      "'conan_export.txz' file format", client.out)

    def test_error_sources_xz(self):
        server = TestServer()
        ref = RecipeReference.loads("pkg/0.1@user/channel")
        ref.revision = "myreciperev"
        client = TestClient(servers={"default": server})
        server.server_store.update_last_revision(ref)
        export = server.server_store.export(ref)
        conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    exports_sources = "*"
"""
        save_files(export, {"conanfile.py": conanfile,
                            "conanmanifest.txt": "1",
                            "conan_sources.txz": "#"})
        client.run("install --requires=pkg/0.1@user/channel --build", assert_error=True)
        self.assertIn("ERROR: This Conan version is not prepared to handle "
                      "'conan_sources.txz' file format", client.out)

    def test_error_package_xz(self):
        server = TestServer()
        ref = RecipeReference.loads("pkg/0.1@user/channel")
        ref.revision = "myreciperev"
        client = TestClient(servers={"default": server})
        server.server_store.update_last_revision(ref)
        export = server.server_store.export(ref)  # *1 the path can't be known before upload a revision
        conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    exports_sources = "*"
"""
        save_files(export, {"conanfile.py": conanfile,
                            "conanmanifest.txt": "1"})
        pref = PkgReference(ref, NO_SETTINGS_PACKAGE_ID, "mypackagerev")
        pref.revision = "mypackagerev"
        server.server_store.update_last_package_revision(pref)

        package = server.server_store.package(pref)
        save_files(package, {"conaninfo.txt": "#",
                             "conanmanifest.txt": "1",
                             "conan_package.txz": "#"})
        client.run("install --requires=pkg/0.1@user/channel", assert_error=True)
        self.assertIn("ERROR: This Conan version is not prepared to handle "
                      "'conan_package.txz' file format", client.out)

    def test(self):
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "a_file.txt")
        save(file_path, "my content!")
        txz = os.path.join(tmp_dir, "sample.tar.xz")
        with tarfile.open(txz, "w:xz") as tar:
            tar.add(file_path, "a_file.txt")

        dest_folder = temp_folder()
        unzip(ConanFileMock(), txz, dest_folder)
        content = load(os.path.join(dest_folder, "a_file.txt"))
        self.assertEqual(content, "my content!")
