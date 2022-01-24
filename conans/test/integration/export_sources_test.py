import copy
import os
import platform
import time
import unittest
from collections import OrderedDict

import pytest
from mock import patch
from parameterized.parameterized import parameterized

from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.paths import EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME
from conans.server.revision_list import RevisionList
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import scan_folder, temp_folder
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, TurboTestClient
from conans.util.files import load, rmdir

conanfile_py = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "hello"
    version = "0.1"
    exports = "*.h", "*.cpp", "*.lic"
    def package(self):
        self.copy("*.h", "include")
"""


combined_conanfile = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "hello"
    version = "0.1"
    exports_sources = "*.h", "*.cpp"
    exports = "*.txt", "*.lic"
    def package(self):
        self.copy("*.h", "include")
        self.copy("data.txt", "docs")
"""


nested_conanfile = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "hello"
    version = "0.1"
    exports_sources = "src/*.h", "src/*.cpp"
    exports = "src/*.txt", "src/*.lic"
    def package(self):
        self.copy("*.h", "include")
        self.copy("*data.txt", "docs")
"""


overlap_conanfile = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "hello"
    version = "0.1"
    exports_sources = "src/*.h", "*.txt"
    exports = "src/*.txt", "*.h", "src/*.lic"
    def package(self):
        self.copy("*.h", "include")
        self.copy("*data.txt", "docs")
"""


class ExportsSourcesTest(unittest.TestCase):

    def setUp(self):
        self.server = TestServer()
        self.other_server = TestServer()
        servers = OrderedDict([("default", self.server),
                               ("other", self.other_server)])
        client = TestClient(servers=servers, inputs=2*["admin", "password"])
        self.client = client
        self.ref = RecipeReference.loads("hello/0.1@lasote/testing")
        self.pref = PkgReference(self.ref, NO_SETTINGS_PACKAGE_ID)

    def _get_folders(self):
        latest_rrev = self.client.cache.get_latest_recipe_reference(self.ref)
        ref_layout = self.client.cache.ref_layout(latest_rrev)
        self.source_folder = ref_layout.source()
        self.export_folder = ref_layout.export()
        self.export_sources_folder = ref_layout.export_sources()

        latest_prev = self.client.cache.get_latest_package_reference(PkgReference(latest_rrev,
                                                                     NO_SETTINGS_PACKAGE_ID))
        if latest_prev:
            pkg_layout = self.client.cache.pkg_layout(latest_prev)
            self.package_folder = pkg_layout.package()

    def _check_source_folder(self, mode):
        """ Source folder MUST be always the same
        """
        expected_sources = ["hello.h"]
        if mode == "both":
            expected_sources.append("data.txt")
        if mode == "nested" or mode == "overlap":
            expected_sources = ["src/hello.h", "src/data.txt"]
        expected_sources = sorted(expected_sources)
        self.assertEqual(scan_folder(self.source_folder), expected_sources)

    def _check_package_folder(self, mode):
        """ Package folder must be always the same (might have tgz after upload)
        """
        if mode in ["exports", "exports_sources"]:
            expected_package = ["conaninfo.txt", "conanmanifest.txt", "include/hello.h"]
        if mode == "both":
            expected_package = ["conaninfo.txt", "conanmanifest.txt", "include/hello.h",
                                "docs/data.txt"]
        if mode == "nested" or mode == "overlap":
            expected_package = ["conaninfo.txt", "conanmanifest.txt", "include/src/hello.h",
                                "docs/src/data.txt"]

        self.assertEqual(scan_folder(self.package_folder), sorted(expected_package))

    def _check_server_folder(self, mode, server=None):
        if mode == "exports_sources":
            expected_server = [EXPORT_SOURCES_TGZ_NAME, 'conanfile.py', 'conanmanifest.txt']
        if mode == "exports":
            expected_server = [EXPORT_TGZ_NAME, 'conanfile.py', 'conanmanifest.txt']
        if mode == "both" or mode == "nested" or mode == "overlap":
            expected_server = [EXPORT_TGZ_NAME, EXPORT_SOURCES_TGZ_NAME, 'conanfile.py',
                               'conanmanifest.txt']

        server = server or self.server
        rev, _ = server.server_store.get_last_revision(self.ref)
        ref = copy.copy(self.ref)
        ref.revision = rev
        self.assertEqual(scan_folder(server.server_store.export(ref)), expected_server)

    def _check_export_folder(self, mode, export_folder=None, export_src_folder=None):
        if mode == "exports_sources":
            expected_src_exports = ["hello.h"]
            expected_exports = ['conanfile.py', 'conanmanifest.txt']
        if mode == "exports":
            expected_src_exports = []
            expected_exports = ["hello.h", 'conanfile.py', 'conanmanifest.txt']
        if mode == "both":
            expected_src_exports = ["hello.h"]
            expected_exports = ['conanfile.py', 'conanmanifest.txt', "data.txt"]
        if mode == "nested":
            expected_src_exports = ["src/hello.h"]
            expected_exports = ["src/data.txt", 'conanfile.py', 'conanmanifest.txt']
        if mode == "overlap":
            expected_src_exports = ["src/hello.h", "src/data.txt"]
            expected_exports = ["src/data.txt", "src/hello.h", 'conanfile.py', 'conanmanifest.txt']

        self.assertEqual(scan_folder(export_folder or self.export_folder),
                         sorted(expected_exports))
        self.assertEqual(scan_folder(export_src_folder or self.export_sources_folder),
                         sorted(expected_src_exports))

    def _check_export_installed_folder(self, mode, updated=False):
        """ Just installed, no EXPORT_SOURCES_DIR is present
        """
        if mode == "exports_sources":
            expected_exports = ['conanfile.py', 'conanmanifest.txt']
        if mode == "both":
            expected_exports = ['conanfile.py', 'conanmanifest.txt', "data.txt"]
        if mode == "exports":
            expected_exports = ['conanfile.py', 'conanmanifest.txt', "hello.h"]
        if mode == "nested":
            expected_exports = ['conanfile.py', 'conanmanifest.txt', "src/data.txt"]
        if mode == "overlap":
            expected_exports = ['conanfile.py', 'conanmanifest.txt', "src/data.txt", "src/hello.h"]
        if updated and mode not in ["exports_sources", "nested", "overlap"]:
            expected_exports.append("license.lic")

        self.assertEqual(scan_folder(self.export_folder), sorted(expected_exports))
        if mode == "exports":
            self.assertFalse(os.path.exists(self.export_sources_folder))

    def _check_export_uploaded_folder(self, mode, export_folder=None, export_src_folder=None):
        if mode == "exports_sources":
            expected_src_exports = ["hello.h"]
            expected_exports = ['conanfile.py', 'conanmanifest.txt']
        if mode == "exports":
            expected_src_exports = []
            expected_exports = ["hello.h", 'conanfile.py', 'conanmanifest.txt']
        if mode == "both":
            expected_src_exports = ["hello.h"]
            expected_exports = ['conanfile.py', 'conanmanifest.txt', "data.txt"]
        if mode == "nested":
            expected_src_exports = ["src/hello.h"]
            expected_exports = ["src/data.txt", 'conanfile.py', 'conanmanifest.txt']

        if mode == "overlap":
            expected_src_exports = ["src/hello.h", "src/data.txt"]
            expected_exports = ["src/data.txt", "src/hello.h", 'conanfile.py', 'conanmanifest.txt']

        export_folder = export_folder or self.export_folder
        self.assertEqual(scan_folder(export_folder), sorted(expected_exports))
        self.assertEqual(scan_folder(export_src_folder or self.export_sources_folder),
                         sorted(expected_src_exports))

    def _check_manifest(self, mode):
        manifest = load(os.path.join(self.client.current_folder,
                                     ".conan_manifests/hello/0.1/lasote/testing/export/"
                                     "conanmanifest.txt"))

        if mode == "exports_sources":
            self.assertIn("%s/hello.h: 5d41402abc4b2a76b9719d911017c592" % EXPORT_SRC_FOLDER,
                          manifest.splitlines())
        elif mode == "exports":
            self.assertIn("hello.h: 5d41402abc4b2a76b9719d911017c592",
                          manifest.splitlines())
        elif mode == "both":
            self.assertIn("data.txt: 8d777f385d3dfec8815d20f7496026dc", manifest.splitlines())
            self.assertIn("%s/hello.h: 5d41402abc4b2a76b9719d911017c592" % EXPORT_SRC_FOLDER,
                          manifest.splitlines())
        elif mode == "nested":
            self.assertIn("src/data.txt: 8d777f385d3dfec8815d20f7496026dc",
                          manifest.splitlines())
            self.assertIn("%s/src/hello.h: 5d41402abc4b2a76b9719d911017c592" % EXPORT_SRC_FOLDER,
                          manifest.splitlines())
        else:
            assert mode == "overlap"
            self.assertIn("src/data.txt: 8d777f385d3dfec8815d20f7496026dc",
                          manifest.splitlines())
            self.assertIn("src/hello.h: 5d41402abc4b2a76b9719d911017c592",
                          manifest.splitlines())
            self.assertIn("%s/src/hello.h: 5d41402abc4b2a76b9719d911017c592" % EXPORT_SRC_FOLDER,
                          manifest.splitlines())
            self.assertIn("%s/src/data.txt: 8d777f385d3dfec8815d20f7496026dc" % EXPORT_SRC_FOLDER,
                          manifest.splitlines())

    def _create_code(self, mode):
        if mode == "exports":
            conanfile = conanfile_py
        elif mode == "exports_sources":
            conanfile = conanfile_py.replace("exports", "exports_sources")
        elif mode == "both":
            conanfile = combined_conanfile
        elif mode == "nested":
            conanfile = nested_conanfile
        elif mode == "overlap":
            conanfile = overlap_conanfile

        if mode in ["nested", "overlap"]:
            self.client.save({"conanfile.py": conanfile,
                              "src/hello.h": "hello",
                              "src/data.txt": "data"})
        else:
            self.client.save({"conanfile.py": conanfile,
                              "hello.h": "hello",
                              "data.txt": "data"})

    @parameterized.expand([("exports", ), ("exports_sources", ), ("both", ), ("nested", ),
                           ("overlap", )])
    def test_export(self, mode):
        self._create_code(mode)

        self.client.run("export . --user=lasote --channel=testing")
        self._get_folders()
        self._check_export_folder(mode)

        # now build package
        self.client.run("install --reference=hello/0.1@lasote/testing --build=missing")
        # Source folder and package should be exatly the same
        self._get_folders()
        self._check_export_folder(mode)
        self._check_source_folder(mode)
        self._check_package_folder(mode)

        # upload to remote
        self.client.run("upload hello/0.1@lasote/testing -r default")
        self._check_export_uploaded_folder(mode)
        self._check_server_folder(mode)

        # remove local
        self.client.run('remove hello/0.1@lasote/testing -f')
        self.assertFalse(os.path.exists(self.export_folder))

        # install from remote
        self.client.run("install --reference=hello/0.1@lasote/testing")
        self.assertFalse(os.path.exists(self.source_folder))
        self._check_export_installed_folder(mode)
        self._check_package_folder(mode)

    @parameterized.expand([("exports", ), ("exports_sources", ), ("both", ), ("nested", ),
                           ("overlap", )])
    def test_export_upload(self, mode):
        self._create_code(mode)

        self.client.run("export . --user=lasote --channel=testing")
        self._get_folders()

        self.client.run("upload hello/0.1@lasote/testing -r default --only-recipe")
        self.assertFalse(os.path.exists(self.source_folder))
        self._check_export_uploaded_folder(mode)
        self._check_server_folder(mode)

        # remove local
        self.client.run('remove hello/0.1@lasote/testing -f')
        self.assertFalse(os.path.exists(self.export_folder))

        # install from remote
        self.client.run("install --reference=hello/0.1@lasote/testing --build")
        self._get_folders()
        self._check_export_folder(mode)
        self._check_source_folder(mode)
        self._check_package_folder(mode)

    @parameterized.expand([("exports", ), ("exports_sources", ), ("both", ), ("nested", ),
                           ("overlap", )])
    def test_reupload(self, mode):
        """ try to reupload to same and other remote
        """
        self._create_code(mode)

        self.client.run("export . --user=lasote --channel=testing")
        self.client.run("install --reference=hello/0.1@lasote/testing --build=missing")
        self.client.run("upload hello/0.1@lasote/testing -r default")
        self.client.run('remove hello/0.1@lasote/testing -f')
        self.client.run("install --reference=hello/0.1@lasote/testing")
        self._get_folders()

        # upload to remote again, the folder remains as installed
        self.client.run("upload hello/0.1@lasote/testing -r default")
        self._check_export_installed_folder(mode)
        self._check_server_folder(mode)

        self.client.run("upload hello/0.1@lasote/testing -r=other")
        self._check_export_uploaded_folder(mode)
        self._check_server_folder(mode, self.other_server)

    @parameterized.expand([("exports", ), ("exports_sources", ), ("both", ), ("nested", ),
                           ("overlap", )])
    def test_update(self, mode):
        self._create_code(mode)

        self.client.run("export . --user=lasote --channel=testing")
        self.client.run("install --reference=hello/0.1@lasote/testing --build=missing")
        self.client.run("upload hello/0.1@lasote/testing -r default")
        self.client.run('remove hello/0.1@lasote/testing -f')
        self.client.run("install --reference=hello/0.1@lasote/testing")

        # upload to remote again, the folder remains as installed
        self.client.run("install --reference=hello/0.1@lasote/testing --update")
        self.assertIn("hello/0.1@lasote/testing: Already installed!", self.client.out)
        self._get_folders()
        self._check_export_installed_folder(mode)

        self.client.save({f"license.lic": "mylicense"})
        self.client.run("create . --user=lasote --channel=testing")

        the_time = time.time() + 10
        with patch.object(RevisionList, '_now', return_value=the_time):
            self.client.run("upload hello/0.1@lasote/testing#latest -r default")

        ref = RecipeReference.loads('hello/0.1@lasote/testing')
        self.client.run(f"remove hello/0.1@lasote/testing"
                        f"#{self.client.cache.get_latest_recipe_reference(ref).revision} -f")

        self.client.run("install --reference=hello/0.1@lasote/testing --update")
        self._get_folders()
        self._check_export_installed_folder(mode, updated=True)


def test_test_package_copied():
    """The exclusion of the test_package folder have been removed so now we test that indeed is
    exported"""

    client = TestClient()
    client.save({"conanfile.py":
                     GenConanfile().with_exports("*").with_exports_sources("*"),
                 "test_package/foo.txt": "bar"})
    client.run("export . --name foo --version 1.0")
    assert "Copied 1 '.txt' file" in client.out


def absolute_existing_folder():
    tmp = temp_folder()
    with open(os.path.join(tmp, "source.cpp"), "a") as _f:
        _f.write("foo")
    return tmp


@pytest.mark.skipif(platform.system() == "Windows", reason="Symlinks not in Windows")
def test_exports_does_not_follow_symlink():
    linked_abs_folder = absolute_existing_folder()
    client = TurboTestClient(default_server_user=True)
    conanfile = GenConanfile().with_package('self.copy("*")').with_exports_sources("*")
    client.save({"conanfile.py": conanfile, "foo.txt": "bar"})
    os.symlink(linked_abs_folder, os.path.join(client.current_folder, "linked_folder"))
    pref = client.create(RecipeReference.loads("lib/1.0"), conanfile=False)
    exports_sources_folder = client.get_latest_ref_layout(pref.ref).export_sources()
    assert os.path.islink(os.path.join(exports_sources_folder, "linked_folder"))
    assert os.path.exists(os.path.join(exports_sources_folder, "linked_folder", "source.cpp"))

    # Check files have been copied to the build
    build_folder = client.get_latest_pkg_layout(pref).build()
    assert os.path.islink(os.path.join(build_folder, "linked_folder"))
    assert os.path.exists(os.path.join(build_folder, "linked_folder", "source.cpp"))

    # Check package files are there
    package_folder = client.get_latest_pkg_layout(pref).package()
    assert os.path.islink(os.path.join(package_folder, "linked_folder"))
    assert os.path.exists(os.path.join(package_folder, "linked_folder", "source.cpp"))

    # Check that the manifest doesn't contain the symlink nor the source.cpp
    contents = load(os.path.join(package_folder, "conanmanifest.txt"))
    assert "foo.txt" in contents
    assert "linked_folder" not in contents
    assert "source.cpp" not in contents

    # Now is a broken link, but the files are not in the cache, just a broken link
    rmdir(linked_abs_folder)
    assert not os.path.exists(os.path.join(exports_sources_folder, "linked_folder", "source.cpp"))
    assert not os.path.exists(os.path.join(build_folder, "linked_folder", "source.cpp"))
    assert not os.path.exists(os.path.join(package_folder, "linked_folder", "source.cpp"))


