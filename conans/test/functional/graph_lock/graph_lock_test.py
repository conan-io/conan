import json
import textwrap
import time
import unittest

from conans.model.graph_lock import LOCKFILE
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.env_reader import get_env


class GraphLockErrorsTest(unittest.TestCase):
    def missing_lock_error_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("install . --lockfile=conan.lock", assert_error=True)
        self.assertIn("ERROR: Missing lockfile in", client.out)

    def update_different_profile_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("install . -if=conf1 -s os=Windows")
        client.run("install . -if=conf2 -s os=Linux")
        client.run("lock update conf1/conan.lock conf2/conan.lock", assert_error=True)
        self.assertIn("Profiles of lockfiles are different", client.out)
        self.assertIn("os=Windows", client.out)
        self.assertIn("os=Linux", client.out)

    def try_to_pass_profile_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("lock create conanfile.py --lockfile-out=conan.lock")
        client.run("install . --lockfile=conan.lock -s os=Windows", assert_error=True)
        self.assertIn("ERROR: Cannot use profile, settings, options or env 'host' "
                      "when using lockfile", client.out)
        client.run("install . --lockfile=conan.lock -pr=default", assert_error=True)
        self.assertIn("ERROR: Cannot use profile, settings, options or env 'host' "
                      "when using lockfile", client.out)
        client.run("install . --lockfile=conan.lock -o myoption=default", assert_error=True)
        self.assertIn("ERROR: Cannot use profile, settings, options or env 'host' "
                      "when using lockfile", client.out)
        client.run("install . --lockfile=conan.lock -s:b os=Windows", assert_error=True)
        self.assertIn("ERROR: Cannot use profile, settings, options or env 'build' "
                      "when using lockfile", client.out)
        client.run("install . --lockfile=conan.lock --profile:build=default", assert_error=True)
        self.assertIn("ERROR: Cannot use profile, settings, options or env 'build' "
                      "when using lockfile", client.out)
        client.run("install . --lockfile=conan.lock -o:b myoption=default", assert_error=True)
        self.assertIn("ERROR: Cannot use profile, settings, options or env 'build' "
                      "when using lockfile", client.out)

    def error_old_format_test(self):
        client = TestClient()
        client.save({"conanfile.txt": ""})
        client.run("install .")
        lockfile = client.load("conan.lock")
        lockfile = lockfile.replace('"0.4"', '"0.1"').replace('"0"', '"UUID"')
        client.save({"conan.lock": lockfile})
        client.run("install . --lockfile=conan.lock", assert_error=True)
        self.assertIn("This lockfile was created with an incompatible version", client.out)

    def error_no_find_test(self):
        client = TestClient()
        client.save({"consumer.txt": ""})
        client.run("lock create consumer.txt --lockfile-out=output.lock")
        client.run("install consumer.txt --lockfile=output.lock")

        client.save({"consumer.py": GenConanfile()})
        client.run("lock create consumer.py --lockfile-out=output.lock "
                   "--name=name --version=version")
        client.run("install consumer.py name/version@ --lockfile=output.lock")
        self.assertIn("consumer.py (name/version): Generated graphinfo", client.out)

    def commands_cannot_create_lockfile_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("export . --lockfile-out=conan.lock", assert_error=True)
        self.assertIn("ERROR: lockfile_out cannot be specified if lockfile is not defined",
                      client.out)
        client.run("install . --lockfile-out=conan.lock", assert_error=True)
        self.assertIn("ERROR: lockfile_out cannot be specified if lockfile is not defined",
                      client.out)
        client.run("info . --lockfile-out=conan.lock", assert_error=True)
        self.assertIn("ERROR: lockfile_out cannot be specified if lockfile is not defined",
                      client.out)
        client.run("create . --lockfile-out=conan.lock", assert_error=True)
        self.assertIn("ERROR: lockfile_out cannot be specified if lockfile is not defined",
                      client.out)


class GraphLockConanfileTXTTest(unittest.TestCase):
    def conanfile_txt_test(self):
        client = TestClient()
        client.save({"conanfile.txt": ""})
        client.run("install .")
        client.run("install . --lockfile=conan.lock")
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

        client2.run("install . --lockfile=conan.lock")
        self.assertIn("pkg/0.1@user/testing from local cache - Cache", client2.out)
        self.assertNotIn("pkg/0.2", client2.out)
        client2.run("install .")
        self.assertIn("pkg/0.2@user/testing from local cache - Cache", client2.out)
        self.assertNotIn("pkg/0.1", client2.out)


class ReproducibleLockfiles(unittest.TestCase):
    def reproducible_lockfile_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("create . PkgA/0.1@user/channel")

        # Use a consumer with a version range
        client.save({"conanfile.py":
                     GenConanfile("PkgB", "0.1").with_require_plain("PkgA/[>=0.1]@user/channel")})
        client.run("lock create conanfile.py --lockfile-out=lock1.lock")
        lockfile = client.load("lock1.lock")
        client.run("lock create conanfile.py --lockfile-out=lock2.lock")
        lockfile2 = client.load("lock2.lock")
        self.assertEqual(lockfile, lockfile2)
        # the default lockfile-out is conan.lock
        client.run("lock create conanfile.py")
        conanlock = client.load("conan.lock")
        self.assertEqual(lockfile, conanlock)
        # different commands still generate identical lock
        client.run("install .")
        info_lock = client.load("conan.lock")
        self.assertEqual(lockfile, info_lock)

    def reproducible_lockfile_txt_test(self):
        client = TestClient()
        client.save({"conanfile.txt": ""})
        client.run("install .")
        lockfile = client.load("conan.lock")
        client.run("install .")
        lockfile2 = client.load("conan.lock")
        self.assertEqual(lockfile, lockfile2)
        # check that the path to local conanfile.txt is relative, reproducible in other machine
        self.assertIn('"path": "conanfile.txt"', lockfile)


@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
class GraphLockRevisionTest(unittest.TestCase):
    rrev_b = "9b64caa2465f7660e6f613b7e87f0cd7"
    pkg_b_id = "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5"
    prev_b = "2ec4fb334e1b4f3fd0a6f66605066ac7"

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

        self._check_lock("PkgB/0.1@user/channel")

        # If we create a new PkgA revision, for example adding info
        pkga = GenConanfile("PkgA", "0.1")
        pkga.with_package_info(cpp_info={"libs": ["mylibPkgA0.1lib"]},
                               env_info={"MYENV": ["myenvPkgA0.1env"]})
        client.save({"conanfile.py": pkga})

        client.run("create . PkgA/0.1@user/channel")
        client.save({"conanfile.py": str(consumer)})

    def _check_lock(self, ref_b, pkg_b_id=None, prev_b=None):
        lockfile = self.client.load(LOCKFILE)
        lock_file_json = json.loads(lockfile)
        self.assertEqual(2, len(lock_file_json["graph_lock"]["nodes"]))
        pkga = lock_file_json["graph_lock"]["nodes"]["1"]
        self.assertEqual(pkga["ref"], "PkgA/0.1@user/channel#fa090239f8ba41ad559f8e934494ee2a")
        pkgb = lock_file_json["graph_lock"]["nodes"]["0"]
        self.assertEqual(pkgb["ref"], ref_b)
        self.assertEqual(pkgb.get("package_id"), pkg_b_id)
        self.assertEqual(pkgb.get("prev"), prev_b)

    def install_info_lock_test(self):
        # Normal install will use it (use install-folder to not change graph-info)
        client = self.client
        client.run("install . -if=tmp")  # Output graph_info to temporary
        client.run("build . -if=tmp")
        self.assertIn("conanfile.py (PkgB/0.1): BUILD DEP LIBS: mylibPkgA0.1lib!!", client.out)

        # Locked install will use PkgA/0.1
        # This is a bit weird, that is necessary to force the --update the get the rigth revision
        client.run("install . -g=cmake --lockfile=conan.lock --lockfile-out=conan.lock --update")
        self._check_lock("PkgB/0.1@user/channel")
        client.run("build .")
        self.assertIn("conanfile.py (PkgB/0.1@user/channel): BUILD DEP LIBS: !!", client.out)

        # Info also works
        client.run("info . --lockfile=conan.lock")
        self.assertIn("Revision: fa090239f8ba41ad559f8e934494ee2a", client.out)

    def export_lock_test(self):
        # locking a version range at export
        self.client.run("export . user/channel --lockfile=conan.lock --lockfile-out=conan.lock")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.rrev_b)

    def create_lock_test(self):
        # Create is also possible
        client = self.client
        client.run("create . PkgB/0.1@user/channel --update --lockfile=conan.lock "
                   "--lockfile-out=conan.lock")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.rrev_b, self.pkg_b_id, self.prev_b)

    def export_pkg_test(self):
        client = self.client
        # Necessary to clean previous revision
        client.run("remove * -f")
        client.run("export-pkg . PkgB/0.1@user/channel --lockfile=conan.lock "
                   "--lockfile-out=conan.lock")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.rrev_b, self.pkg_b_id, self.prev_b)


@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
class RevisionsUpdateTest(unittest.TestCase):

    def test_revisions_update(self):
        # https://github.com/conan-io/conan/issues/7333
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("create . ")
        self.assertIn("PkgA/0.1: Exported revision: fa090239f8ba41ad559f8e934494ee2", client.out)
        client.run("upload * --all --confirm")
        client.run("search PkgA/0.1@ --revisions -r=default")
        self.assertIn("fa090239f8ba41ad559f8e934494ee2a", client.out)

        client2 = TestClient(servers=client.servers, users=client.users)
        client2.save({"conanfile.py": GenConanfile("PkgA", "0.1").with_build_msg("Building")})
        time.sleep(1)
        client2.run("create . ")
        self.assertIn("PkgA/0.1: Exported revision: 7f1110e1ae8d852b6d55f7f121864de6", client2.out)
        client2.run("upload * --all --confirm")
        client2.run("search PkgA/0.1@ --revisions -r=default")
        self.assertIn("fa090239f8ba41ad559f8e934494ee2a", client2.out)
        self.assertIn("7f1110e1ae8d852b6d55f7f121864de6", client2.out)

        client.save({"conanfile.py": GenConanfile("PkgB", "0.1").with_require_plain("PkgA/0.1")})
        client.run("lock create conanfile.py --update --lockfile-out=conan.lock")
        self.assertIn("PkgA/0.1: Downloaded recipe revision 7f1110e1ae8d852b6d55f7f121864de6",
                      client.out)
        lockfile = client.load("conan.lock")
        self.assertIn("7f1110e1ae8d852b6d55f7f121864de6", lockfile)

        # Put again the old revision locally
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("create . ")
        self.assertIn("PkgA/0.1: Exported revision: fa090239f8ba41ad559f8e934494ee2", client.out)

        # Local revisions are not updated, even with a lockfile, unless --update
        client.save({"conanfile.py": GenConanfile("PkgB", "0.1").with_require_plain("PkgA/0.1")})
        client.run("install . --lockfile=conan.lock", assert_error=True)
        self.assertIn("ERROR: The 'fa090239f8ba41ad559f8e934494ee2a' revision recipe in the "
                      "local cache", client.out)
        client.run("install . --lockfile=conan.lock --update")
        self.assertIn("PkgA/0.1: Downloaded recipe revision 7f1110e1ae8d852b6d55f7f121864de6",
                      client.out)

    def test_version_ranges_revisions_update(self):
        # https://github.com/conan-io/conan/issues/7333
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . PkgA/0.1@")
        self.assertIn("PkgA/0.1: Exported revision: f3367e0e7d170aa12abccb175fee5f97", client.out)
        client.run("upload * --all --confirm")
        client.run("search PkgA/0.1@ --revisions -r=default")
        self.assertIn("f3367e0e7d170aa12abccb175fee5f97", client.out)

        client2 = TestClient(servers=client.servers, users=client.users)
        client2.save({"conanfile.py": GenConanfile("PkgA")})
        client2.run("create . PkgA/0.2@")
        client2.run("upload * --all --confirm")
        client2.save({"conanfile.py": GenConanfile("PkgA", "0.2").with_build_msg("Building")})
        time.sleep(1)
        client2.run("create . ")
        self.assertIn("PkgA/0.2: Exported revision: 5e8148093372278be4e8d8e831d8bdb6", client2.out)
        client2.run("upload * --all --confirm")
        client2.run("search PkgA/0.2@ --revisions -r=default")
        self.assertIn("5e8148093372278be4e8d8e831d8bdb6", client2.out)
        self.assertIn("8ec297bab84c88218d1db36ffea97d0e", client2.out)

        client.save({"conanfile.py": GenConanfile("PkgB", "0.1").with_require_plain("PkgA/[>=0.1]")})
        client.run("lock create conanfile.py --update --lockfile-out=conan.lock")
        self.assertIn("PkgA/0.2: Downloaded recipe revision 5e8148093372278be4e8d8e831d8bdb6",
                      client.out)
        lockfile = client.load("conan.lock")
        self.assertIn("5e8148093372278be4e8d8e831d8bdb6", lockfile)

        # Put again the old revision locally
        client.run("remove * -f")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . PkgA/0.1@")
        self.assertIn("PkgA/0.1: Exported revision: f3367e0e7d170aa12abccb175fee5f97", client.out)

        client.save({"conanfile.py": GenConanfile("PkgB", "0.1").with_require_plain("PkgA/[>=0.1]")})
        client.run("install . --lockfile=conan.lock")
        self.assertIn("PkgA/0.2: Downloaded recipe revision 5e8148093372278be4e8d8e831d8bdb6",
                      client.out)


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

        client.run("lock create --reference=nano/1.0@ --build --lockfile-out=conan.lock")
        lockfile = client.load("conan.lock")
        self.assertIn('"options": "variation=nano"', lockfile)
        client.run("create ffmepg ffmpeg/1.0@ --build --lockfile=conan.lock")
        self.assertIn("ffmpeg/1.0: Requirements: Variation nano!!", client.out)


class GraphInstallArgumentsUpdated(unittest.TestCase):

    def test_lockfile_argument_updated_install(self):
        # https://github.com/conan-io/conan/issues/6845
        # --lockfile parameter is not updated after install and
        # outputs results to conan.lock
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . somelib/1.0@")
        client.run("lock create --reference=somelib/1.0@ --lockfile-out=somelib.lock")
        previous_lock = client.load("somelib.lock")
        # This should fail, because somelib is locked
        client.run("install somelib/1.0@ --lockfile=somelib.lock --build somelib", assert_error=True)
        self.assertIn("Cannot build 'somelib/1.0#f3367e0e7d170aa12abccb175fee5f97' because it "
                      "is already locked in the input lockfile", client.out)
        new_lock = client.load("somelib.lock")
        self.assertEqual(previous_lock, new_lock)


class BuildLockedTest(unittest.TestCase):
    def test_build_locked_node(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . flac/1.0@")
        client.run("lock create --reference=flac/1.0@ --lockfile-out=conan.lock --build")
        lock = json.loads(client.load("conan.lock"))
        flac = lock["graph_lock"]["nodes"]["1"]
        if client.cache.config.revisions_enabled:
            ref = "flac/1.0#f3367e0e7d170aa12abccb175fee5f97"
            prev = "83c38d3b4e5f1b8450434436eec31b00"
        else:
            ref = "flac/1.0"
            prev = "0"
        self.assertEqual(flac["ref"], ref)
        self.assertEqual(flac["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertIsNone(flac.get("prev"))

        client.run("install flac/1.0@ --lockfile=conan.lock --lockfile-out=output.lock")
        lock = json.loads(client.load("output.lock"))
        flac = lock["graph_lock"]["nodes"]["1"]
        self.assertEqual(flac["ref"], ref)
        self.assertEqual(flac["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertIsNone(flac.get("prev"))

        client.run("install flac/1.0@ --build=flac --lockfile=conan.lock --lockfile-out=output.lock")
        lock = json.loads(client.load("output.lock"))
        flac = lock["graph_lock"]["nodes"]["1"]
        self.assertEqual(flac["ref"], ref)
        self.assertEqual(flac["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(flac["prev"], prev)
