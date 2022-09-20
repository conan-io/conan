import json
import textwrap
import time
import unittest

import pytest

from conans.model.graph_lock import LOCKFILE
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.env_reader import get_env


class GraphLockErrorsTest(unittest.TestCase):
    def test_missing_lock_error(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("install . --lockfile=conan.lock", assert_error=True)
        self.assertIn("ERROR: Missing lockfile in", client.out)

    def test_update_different_profile(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("install . -if=conf1 -s os=Windows")
        client.run("install . -if=conf2 -s os=Linux")
        client.run("lock update conf1/conan.lock conf2/conan.lock", assert_error=True)
        self.assertIn("Profiles of lockfiles are different", client.out)
        self.assertIn("os=Windows", client.out)
        self.assertIn("os=Linux", client.out)

    def test_try_to_pass_profile(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("lock create conanfile.py --lockfile-out=conan.lock")
        client.run("install . --lockfile=conan.lock -s os=Windows", assert_error=True)
        self.assertIn("ERROR: Cannot use profile, settings, options, env or conf 'host' "
                      "when using lockfile", client.out)
        client.run("install . --lockfile=conan.lock -pr=default", assert_error=True)
        self.assertIn("ERROR: Cannot use profile, settings, options, env or conf 'host' "
                      "when using lockfile", client.out)
        client.run("install . --lockfile=conan.lock -o myoption=default", assert_error=True)
        self.assertIn("ERROR: Cannot use profile, settings, options, env or conf 'host' "
                      "when using lockfile", client.out)
        client.run("install . --lockfile=conan.lock -s:b os=Windows", assert_error=True)
        self.assertIn("ERROR: Cannot use profile, settings, options, env or conf 'build' "
                      "when using lockfile", client.out)
        client.run("install . --lockfile=conan.lock --profile:build=default", assert_error=True)
        self.assertIn("ERROR: Cannot use profile, settings, options, env or conf 'build' "
                      "when using lockfile", client.out)
        client.run("install . --lockfile=conan.lock -o:b myoption=default", assert_error=True)
        self.assertIn("ERROR: Cannot use profile, settings, options, env or conf 'build' "
                      "when using lockfile", client.out)
        client.run("install . --lockfile=conan.lock -c:b core:required_conan_version=>=1.36",
                   assert_error=True)
        self.assertIn("ERROR: Cannot use profile, settings, options, env or conf 'build' "
                      "when using lockfile", client.out)

    def test_error_old_format(self):
        client = TestClient()
        client.save({"conanfile.txt": ""})
        client.run("install .")
        lockfile = client.load("conan.lock")
        lockfile = lockfile.replace('"0.4"', '"0.1"').replace('"0"', '"UUID"')
        client.save({"conan.lock": lockfile})
        client.run("install . --lockfile=conan.lock", assert_error=True)
        self.assertIn("This lockfile was created with an incompatible version", client.out)

    def test_error_no_find(self):
        client = TestClient()
        client.save({"consumer.txt": ""})
        client.run("lock create consumer.txt --lockfile-out=output.lock")
        client.run("install consumer.txt --lockfile=output.lock")

        client.save({"consumer.py": GenConanfile()})
        client.run("lock create consumer.py --lockfile-out=output.lock "
                   "--name=name --version=version")
        client.run("install consumer.py name/version@ --lockfile=output.lock")
        self.assertIn("consumer.py (name/version): Generated graphinfo", client.out)

    @staticmethod
    def test_error_no_filename():
        # https://github.com/conan-io/conan/issues/8675
        client = TestClient()
        client.save({"consumer.txt": ""})
        client.run("lock create .", assert_error=True)
        assert "RROR: Path argument must include filename like 'conanfile.py'" in client.out

    def test_commands_cannot_create_lockfile(self):
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

    def test_cannot_create_twice(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("lock create conanfile.py --lockfile-out=conan.lock")
        client.run("create . --lockfile=conan.lock --lockfile-out=conan.lock")
        client.run("install PkgA/0.1@ --build=PkgA --lockfile=conan.lock --lockfile-out=conan.lock",
                   assert_error=True)
        rev = "#fa090239f8ba41ad559f8e934494ee2a" if client.cache.config.revisions_enabled else ""
        self.assertIn("Cannot build 'PkgA/0.1{}' because it is already locked".format(rev),
                      client.out)

        client.run("create . --lockfile=conan.lock --lockfile-out=conan.lock", assert_error=True)
        self.assertIn("ERROR: Attempt to modify locked PkgA/0.1", client.out)


class GraphLockConanfileTXTTest(unittest.TestCase):
    def test_conanfile_txt(self):
        client = TestClient()
        client.save({"conanfile.txt": ""})
        client.run("install .")
        client.run("install . --lockfile=conan.lock")
        self.assertIn("Using lockfile", client.out)

    def test_conanfile_txt_deps(self):
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
    def test_reproducible_lockfile(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("create . PkgA/0.1@user/channel")

        # Use a consumer with a version range
        client.save({"conanfile.py":
                     GenConanfile("PkgB", "0.1").with_require("PkgA/[>=0.1]@user/channel")})
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

    def test_reproducible_lockfile_txt(self):
        client = TestClient()
        client.save({"conanfile.txt": ""})
        client.run("install .")
        lockfile = client.load("conan.lock")
        client.run("install .")
        lockfile2 = client.load("conan.lock")
        self.assertEqual(lockfile, lockfile2)
        # check that the path to local conanfile.txt is relative, reproducible in other machine
        self.assertIn('"path": "conanfile.txt"', lockfile)


@pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
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

    def test_install_info_lock(self):
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

    def test_export_lock(self):
        # locking a version range at export
        self.client.run("export . user/channel --lockfile=conan.lock --lockfile-out=conan.lock")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.rrev_b)

    def test_create_lock(self):
        # Create is also possible
        client = self.client
        client.run("create . PkgB/0.1@user/channel --update --lockfile=conan.lock "
                   "--lockfile-out=conan.lock")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.rrev_b, self.pkg_b_id, self.prev_b)

    def test_export_pkg(self):
        client = self.client
        # Necessary to clean previous revision
        client.run("remove * -f")
        client.run("export-pkg . PkgB/0.1@user/channel --lockfile=conan.lock "
                   "--lockfile-out=conan.lock")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.rrev_b, self.pkg_b_id, self.prev_b)


@pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
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

        client.save({"conanfile.py": GenConanfile("PkgB", "0.1").with_require("PkgA/0.1")})
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
        client.save({"conanfile.py": GenConanfile("PkgB", "0.1").with_require("PkgA/0.1")})
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

        client.save({"conanfile.py": GenConanfile("PkgB", "0.1").with_require("PkgA/[>=0.1]")})
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

        client.save({"conanfile.py": GenConanfile("PkgB", "0.1").with_require("PkgA/[>=0.1]")})
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

    def test_base_options(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_option("shared", [True, False])
                                                   .with_default_option("shared", False)})
        client.run("create . pkg/0.1@")
        client.run("lock create --reference=pkg/0.1 --base --lockfile-out=pkg_base.lock")
        client.run("lock create --reference=pkg/0.1 --lockfile=pkg_base.lock "
                   "--lockfile-out=pkg.lock -o pkg:shared=True")
        pkg_lock = client.load("pkg.lock")
        self.assertIn('"options": "shared=True"', pkg_lock)
        client.run("lock create --reference=pkg/0.1 --lockfile=pkg_base.lock "
                   "--lockfile-out=pkg.lock -o pkg:shared=False")
        pkg_lock = client.load("pkg.lock")
        self.assertIn('"options": "shared=False"', pkg_lock)

    def test_config_option(self):
        # https://github.com/conan-io/conan/issues/7991
        client = TestClient()
        pahomqttc = textwrap.dedent("""
            from conans import ConanFile
            class PahoMQTCC(ConanFile):
                options = {"shared": [True, False]}
                default_options = {"shared": False}

                def config_options(self):
                    # This is weaker than "configure()", will be overwritten by downstream
                    self.options.shared = True
            """)

        pahomqttcpp = textwrap.dedent("""
            from conans import ConanFile
            class Meta(ConanFile):
                requires = "pahomqttc/1.0"
                def configure(self):
                    self.options["pahomqttc"].shared = False
            """)

        client.save({"pahomqttc/conanfile.py": pahomqttc,
                     "pahomqttcpp/conanfile.py": pahomqttcpp,
                     "consumer/conanfile.txt": "[requires]\npahomqttcpp/1.0"})
        client.run("export pahomqttc pahomqttc/1.0@")
        client.run("export pahomqttcpp pahomqttcpp/1.0@")

        client.run("install consumer/conanfile.txt --build -o paho-mqtt-c:shared=False")
        lockfile = client.load("conan.lock")
        self.assertIn('"options": "pahomqttc:shared=False"', lockfile)
        self.assertNotIn('shared=True', lockfile)
        client.run("install consumer/conanfile.txt --lockfile=conan.lock")

    def test_configure(self):
        # https://github.com/conan-io/conan/issues/7991
        client = TestClient()
        pahomqttc = textwrap.dedent("""
            from conans import ConanFile
            class PahoMQTCC(ConanFile):
                options = {"shared": [True, False]}
                default_options = {"shared": False}

                def configure(self):
                    self.options.shared = True
            """)

        pahomqttcpp = textwrap.dedent("""
            from conans import ConanFile
            class Meta(ConanFile):
                requires = "pahomqttc/1.0"
                def configure(self):
                    self.options["pahomqttc"].shared = False
            """)

        client.save({"pahomqttc/conanfile.py": pahomqttc,
                     "pahomqttcpp/conanfile.py": pahomqttcpp,
                     "consumer/conanfile.txt": "[requires]\npahomqttcpp/1.0"})
        client.run("export pahomqttc pahomqttc/1.0@")
        client.run("export pahomqttcpp pahomqttcpp/1.0@")

        client.run("install consumer/conanfile.txt --build -o paho-mqtt-c:shared=False")
        lockfile = client.load("conan.lock")
        self.assertIn('"options": "pahomqttc:shared=True"', lockfile)
        # Check the trailing ", to not get the profile one
        self.assertNotIn('shared=False"', lockfile)
        client.run("install consumer/conanfile.txt --lockfile=conan.lock")


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
        rev = "#f3367e0e7d170aa12abccb175fee5f97" if client.cache.config.revisions_enabled else ""
        self.assertIn("Cannot build 'somelib/1.0{}' because it "
                      "is already locked in the input lockfile".format(rev), client.out)
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


class AddressRootNodetest(unittest.TestCase):
    def test_find_root_node(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.errors import ConanInvalidConfiguration

            class Pkg(ConanFile):
                def set_name(self):
                    self.name = "pkg"

                def set_version(self):
                    self.version = "0.1"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("lock create conanfile.py --lockfile-out=conan.lock")
        client.run("install . --lockfile=conan.lock")
        self.assertIn("conanfile.py (pkg/0.1): Installing package", client.out)


def test_error_test_command():
    # https://github.com/conan-io/conan/issues/9088
    client = TestClient()
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": GenConanfile().with_requires("dep/[>=1.0]"),
                 "test_package/conanfile.py": GenConanfile().with_test("pass")})
    client.run("create dep dep/1.0@")
    client.run("create pkg pkg/1.0@")
    client.run("lock create --ref=pkg/1.0@")
    client.run("create dep dep/1.1@")
    client.run("test test_package pkg/1.0@ --lockfile=conan.lock")
    assert "dep/1.0" in client.out
    assert "dep/1.1" not in client.out
    client.run("test test_package pkg/1.0@")
    assert "dep/1.0" not in client.out
    assert "dep/1.1" in client.out


def test_override_not_locked():
    # https://github.com/conan-io/conan/pull/8907
    client = TestClient()
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": GenConanfile().with_requires("dep/[*]"),
                 "consumer/conanfile.py":
                     GenConanfile().with_requirement("pkg/1.0").with_requirement("dep/1.0",
                                                                                 override=True)})
    client.run("create dep dep/1.0@")
    client.run("create dep dep/1.1@")
    client.run("create pkg pkg/1.0@")
    client.run("lock create consumer/conanfile.py --lockfile-out=app1.lock")
    client.run("install consumer/conanfile.py --lockfile app1.lock")


def test_compatible_transient_options():
    # https://github.com/conan-io/conan/issues/9591
    client = TestClient()

    lib_base = GenConanfile().with_option("shared", [True, False])\
        .with_default_option("shared", False)

    lib_compatible = textwrap.dedent("""
        from conans import ConanFile
        class LibCompatibleConanFile(ConanFile):
            settings = "os"
            options = {"shared": [True, False]}
            default_options = {"shared": False}
            requires = "base/1.0"
            def package_id(self):
                if self.settings.os == "Windows":
                    compatible_pkg = self.info.clone()
                    compatible_pkg.settings.os = "Linux"
                    self.compatible_packages.append(compatible_pkg)
        """)
    consumer = GenConanfile().with_requires("compatible/1.0")
    client.save({"base/conanfile.py": lib_base,
                 "compat/conanfile.py": lib_compatible,
                 "consumer/conanfile.py": consumer})
    client.run("create base base/1.0@")
    client.run("create compat compatible/1.0@ -s os=Linux")
    client.run("lock create consumer/conanfile.py -s os=Windows --lockfile-out=deps.lock")
    client.run("install consumer/conanfile.py --lockfile=deps.lock")
