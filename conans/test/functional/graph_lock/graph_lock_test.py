import json
import textwrap
import unittest

from conans.model.graph_lock import LOCKFILE, LOCKFILE_VERSION
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.env_reader import get_env


class GraphLockErrorsTest(unittest.TestCase):
    def missing_lock_error_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("install . --lockfile", assert_error=True)
        self.assertIn("ERROR: Missing lockfile in", client.out)

    def update_different_profile_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("install . -if=conf1 -s os=Windows")
        client.run("install . -if=conf2 -s os=Linux")
        client.run("graph update-lock conf1 conf2", assert_error=True)
        self.assertIn("Profiles of lockfiles are different", client.out)
        self.assertIn("os=Windows", client.out)
        self.assertIn("os=Linux", client.out)

    def error_old_format_test(self):
        client = TestClient()
        client.save({"conanfile.txt": ""})
        client.run("install .")
        lockfile = client.load("conan.lock")
        lockfile = lockfile.replace('"0.4"', '"0.1"').replace('"0"', '"UUID"')
        client.save({"conan.lock": lockfile})
        client.run("install . --lockfile", assert_error=True)
        self.assertIn("This lockfile was created with an incompatible version", client.out)


class GraphLockConanfileTXTTest(unittest.TestCase):
    def conanfile_txt_test(self):
        client = TestClient()
        client.save({"conanfile.txt": ""})
        client.run("install .")
        client.run("install . --lockfile")
        self.assertIn("Using lockfile", client.out)

    def conanfile_txt_deps_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . pkg/0.1@user/testing")

        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.txt": "[requires]\npkg/[>0.0]@user/testing"})
        client2.run("install .")
        self.assertIn("pkg/0.1@user/testing from local cache - Cache", client2.out)

        client.run("create . pkg/0.2@user/testing")

        client2.run("install . --lockfile")
        self.assertIn("pkg/0.1@user/testing from local cache - Cache", client2.out)
        self.assertNotIn("pkg/0.2", client2.out)
        client2.run("install .")
        self.assertIn("pkg/0.2@user/testing from local cache - Cache", client2.out)
        self.assertNotIn("pkg/0.1", client2.out)


class GraphLockCustomFilesTest(unittest.TestCase):

    def _check_lock(self):
        lock_file = self.client.load("custom.lock")
        lock_file_json = json.loads(lock_file)
        self.assertEqual(lock_file_json["version"], LOCKFILE_VERSION)
        nodes = lock_file_json["graph_lock"]["nodes"]
        self.assertEqual(2, len(nodes))
        pkg_a = nodes["1"]
        pkg_b = nodes["0"]
        if self.client.cache.config.revisions_enabled:
            self.assertEqual(pkg_a["ref"], "PkgA/0.1@user/channel#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(pkg_a["prev"], "83c38d3b4e5f1b8450434436eec31b00")
        else:
            self.assertEqual(pkg_a["ref"], "PkgA/0.1@user/channel")
            self.assertEqual(pkg_a["prev"], "0")

        self.assertEqual(pkg_a["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(pkg_b["ref"], "PkgB/0.1")
        self.assertIsNone(pkg_b.get("package_id"))
        self.assertIsNone(pkg_b.get("prev"))

    def test(self):
        client = TestClient()
        self.client = client
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . PkgA/0.1@user/channel")

        # Use a consumer with a version range
        consumer = GenConanfile("PkgB", "0.1").with_require_plain("PkgA/[>=0.1]@user/channel")
        client.save({"conanfile.py": consumer})
        client.run("graph lock . --lockfile=custom.lock")
        self.assertIn("PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                      client.out)
        self._check_lock()

        # If we create a new PkgA version
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . PkgA/0.2@user/channel")
        client.save({"conanfile.py": consumer})
        client.run("install . --lockfile=custom.lock")
        self._check_lock()


class ReproducibleLockfiles(unittest.TestCase):
    def reproducible_lockfile_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("create . PkgA/0.1@user/channel")

        # Use a consumer with a version range
        client.save({"conanfile.py":
                     GenConanfile("PkgB", "0.1").with_require_plain("PkgA/[>=0.1]@user/channel")})
        client.run("graph lock .")
        lockfile = client.load(LOCKFILE)
        client.run("graph lock .")
        lockfile2 = client.load(LOCKFILE)
        self.assertEqual(lockfile, lockfile2)
        # different commands still generate identical lock
        client.run("info . --install-folder=info")
        info_lock = client.load("info/conan.lock")
        self.assertEqual(lockfile, info_lock)
        client.run("install . --install-folder=install")
        info_lock = client.load("install/conan.lock")
        self.assertEqual(lockfile, info_lock)

    def reproducible_lockfile_txt_test(self):
        client = TestClient()
        client.save({"conanfile.txt": ""})
        client.run("install .")
        lockfile = client.load("conan.lock")
        client.run("install .")
        lockfile2 = client.load("conan.lock")
        self.assertEqual(lockfile, lockfile2)


@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
class GraphLockRevisionTest(unittest.TestCase):
    pkg_b_revision = "9b64caa2465f7660e6f613b7e87f0cd7"
    pkg_b_id = "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5"
    pkg_b_package_revision = "#2ec4fb334e1b4f3fd0a6f66605066ac7"

    def setUp(self):
        client = TestClient(default_server_user=True)
        # Important to activate revisions
        self.client = client
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("create . PkgA/0.1@user/channel")
        client.run("upload PkgA/0.1@user/channel --all")

        consumer = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                name = "PkgB"
                version = "0.1"
                requires = "PkgA/0.1@user/channel"
                def build(self):
                    self.output.info("BUILD DEP LIBS: %s!!" % ",".join(self.deps_cpp_info.libs))
                def package_info(self):
                    self.output.info("PACKAGE_INFO DEP LIBS: %s!!"
                                     % ",".join(self.deps_cpp_info.libs))
            """)
        client.save({"conanfile.py": str(consumer)})
        client.run("install . PkgB/0.1@user/channel")

        self._check_lock("PkgB/0.1@")

        # If we create a new PkgA revision, for example adding info
        pkga = GenConanfile("PkgA", "0.1")
        pkga.with_package_info(cpp_info={"libs": ["mylibPkgA0.1lib"]},
                               env_info={"MYENV": ["myenvPkgA0.1env"]})
        client.save({"conanfile.py": pkga})

        client.run("create . PkgA/0.1@user/channel")
        client.save({"conanfile.py": str(consumer)})

    def _check_lock(self, ref_b, rev_b=""):
        lockfile = self.client.load(LOCKFILE)
        lock_file_json = json.loads(lockfile)
        self.assertEqual(2, len(lock_file_json["graph_lock"]["nodes"]))
        pkga = lock_file_json["graph_lock"]["nodes"]["1"]
        self.assertEqual(pkga["ref"], "PkgA/0.1@user/channel#fa090239f8ba41ad559f8e934494ee2a")

    def install_info_lock_test(self):
        # Normal install will use it (use install-folder to not change graph-info)
        client = self.client
        client.run("install . -if=tmp")  # Output graph_info to temporary
        client.run("build . -if=tmp")
        self.assertIn("conanfile.py (PkgB/0.1): BUILD DEP LIBS: mylibPkgA0.1lib!!", client.out)

        # Locked install will use PkgA/0.1
        # This is a bit weird, that is necessary to force the --update the get the rigth revision
        client.run("install . -g=cmake --lockfile --update")
        self._check_lock("PkgB/0.1@")
        client.run("build .")
        self.assertIn("conanfile.py (PkgB/0.1@user/channel): BUILD DEP LIBS: !!", client.out)

        # Info also works
        client.run("info . --lockfile")
        self.assertIn("Revision: fa090239f8ba41ad559f8e934494ee2a", client.out)

    def export_lock_test(self):
        # locking a version range at export
        self.client.run("export . user/channel --lockfile")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.pkg_b_revision)

    def create_lock_test(self):
        # Create is also possible
        client = self.client
        client.run("create . PkgB/0.1@user/channel --update --lockfile")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.pkg_b_revision,
                         self.pkg_b_package_revision)

    def export_pkg_test(self):
        client = self.client
        # Necessary to clean previous revision
        client.run("remove * -f")
        client.run("export-pkg . PkgB/0.1@user/channel --lockfile")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.pkg_b_revision,
                         self.pkg_b_package_revision)


class LockFileOptionsTest(unittest.TestCase):
    def test_options(self):
        client = TestClient()
        ffmpeg = textwrap.dedent("""
            from conans import ConanFile
            class FfmpegConan(ConanFile):
                options = {"variation": ["standard", "nano"]}
                default_options = {"variation": "standard"}

                def requirements(self):
                    variation = str(self.options.variation)
                    self.output.info("Requirements: Variation %s!!" % variation)
                    if self.options.variation == "standard":
                        self.requires("missingdep/1.0")
            """)

        variant = textwrap.dedent("""
            from conans import ConanFile
            class Meta(ConanFile):
                requires = "ffmpeg/1.0"
                default_options = {"ffmpeg:variation": "nano"}
            """)

        client.save({"ffmepg/conanfile.py": ffmpeg,
                     "variant/conanfile.py": variant})
        client.run("export ffmepg ffmpeg/1.0@")
        client.run("export variant nano/1.0@")

        client.run("graph lock nano/1.0@ --build")
        lockfile = client.load("conan.lock")
        self.assertIn('"options": "variation=nano"', lockfile)
        client.run("create ffmepg ffmpeg/1.0@ --build --lockfile")
        self.assertIn("ffmpeg/1.0: Requirements: Variation nano!!", client.out)


class GraphInstallArgumentsUpdated(unittest.TestCase):

    def test_lockfile_argument_updated_install(self):
        # https://github.com/conan-io/conan/issues/6845
        # --lockfile parameter is not updated after install and
        # outputs results to conan.lock
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . somelib/1.0@")
        client.run("graph lock somelib/1.0@ --lockfile=somelib.lock")
        previous_lock = client.load("somelib.lock")
        # This should fail, because somelib is locked
        client.run("install somelib/1.0@ --lockfile=somelib.lock --build somelib", assert_error=True)
        self.assertIn("Trying to build 'somelib/1.0#f3367e0e7d170aa12abccb175fee5f97', "
                      "but it is locked", client.out)
        new_lock = client.load("somelib.lock")
        self.assertEqual(previous_lock, new_lock)
