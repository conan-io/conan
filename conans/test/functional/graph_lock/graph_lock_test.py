import json
import os
import textwrap
import unittest

from conans.model.graph_lock import LOCKFILE, LOCKFILE_VERSION
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TestServer, GenConanfile
from conans.util.files import load


class GraphLockErrorsTest(unittest.TestCase):
    def missing_lock_error_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("PkgA").with_version("0.1")})
        client.run("install . --lockfile", assert_error=True)
        self.assertIn("ERROR: Missing lockfile in", client.out)

    def update_different_profile_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("PkgA").with_version("0.1")})
        client.run("install . -if=conf1 -s os=Windows")
        client.run("install . -if=conf2 -s os=Linux")
        client.run("graph update-lock conf1 conf2", assert_error=True)
        self.assertIn("Profiles of lockfiles are different", client.out)
        self.assertIn("os=Windows", client.out)
        self.assertIn("os=Linux", client.out)


class GraphLockCustomFilesTest(unittest.TestCase):
    consumer = GenConanfile().with_name("PkgB").with_version("0.1")\
                             .with_require_plain("PkgA/[>=0.1]@user/channel")
    pkg_b_revision = "180919b324d7823f2683af9381d11431"
    pkg_b_id = "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5"
    pkg_b_package_revision = "#2913f67cea630aee496fe70fd38b5b0f"

    def _check_lock(self, ref_b, rev_b=""):
        ref_b = repr(ConanFileReference.loads(ref_b))
        lock_file = load(os.path.join(self.client.current_folder, "custom.lock"))
        lock_file_json = json.loads(lock_file)
        self.assertEqual(lock_file_json["version"], LOCKFILE_VERSION)
        self.assertEqual(2, len(lock_file_json["graph_lock"]["nodes"]))
        self.assertIn("PkgA/0.1@user/channel#fa090239f8ba41ad559f8e934494ee2a:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#0d561e10e25511b9bfa339d06360d7c1",
                      lock_file)
        self.assertIn('"%s:%s%s"' % (ref_b, self.pkg_b_id, rev_b), lock_file)

    def test(self):
        client = TestClient()
        self.client = client
        client.save({"conanfile.py": GenConanfile().with_name("PkgA").with_version("0.1")})
        client.run("create . PkgA/0.1@user/channel")

        # Use a consumer with a version rang
        client.save({"conanfile.py": self.consumer})
        client.run("graph lock . --lockfile=custom.lock")
        self._check_lock("PkgB/0.1@")

        # If we create a new PkgA version
        client.save({"conanfile.py": GenConanfile().with_name("PkgA").with_version("0.2")})
        client.run("create . PkgA/0.2@user/channel")
        client.save({"conanfile.py": self.consumer})
        client.run("install . --lockfile=custom.lock")
        self._check_lock("PkgB/0.1@")


class GraphLockVersionRangeTest(unittest.TestCase):
    consumer = GenConanfile().with_name("PkgB").with_version("0.1")\
                             .with_require_plain("PkgA/[>=0.1]@user/channel")
    pkg_b_revision = "e8cabe5f1c737bcb8223b667f071842d"
    pkg_b_id = "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5"
    pkg_b_package_revision = "#97d1695f4e456433cc5a1dfa14655a0f"
    modified_pkg_b_revision = "6073b7f447ba8d88f43a610a15481f2a"
    modified_pkg_b_package_revision = "#ecc8f5e8fbe7847fbd9673ddd29f4f10"
    graph_lock_command = "install ."

    def setUp(self):
        client = TestClient()
        self.client = client
        client.save({"conanfile.py": GenConanfile().with_name("PkgA").with_version("0.1")})
        client.run("create . PkgA/0.1@user/channel")

        # Use a consumer with a version range
        client.save({"conanfile.py": str(self.consumer)})
        client.run(self.graph_lock_command)

        self._check_lock("PkgB/0.1@")

        # If we create a new PkgA version
        client.save({"conanfile.py": GenConanfile().with_name("PkgA").with_version("0.2")})
        client.run("create . PkgA/0.2@user/channel")
        client.save({"conanfile.py": str(self.consumer)})

    def _check_lock(self, ref_b, rev_b=""):
        lock_file = load(os.path.join(self.client.current_folder, LOCKFILE))
        lock_file_json = json.loads(lock_file)
        self.assertEqual(2, len(lock_file_json["graph_lock"]["nodes"]))
        self.assertIn("PkgA/0.1@user/channel#fa090239f8ba41ad559f8e934494ee2a:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#0d561e10e25511b9bfa339d06360d7c1",
                      lock_file)
        self.assertIn('"%s:%s%s"' % (repr(ConanFileReference.loads(ref_b)), self.pkg_b_id, rev_b), lock_file)

    def install_info_lock_test(self):
        # Normal install will use it (use install-folder to not change graph-info)
        client = self.client
        client.run("install . -if=tmp")  # Output graph_info to temporary
        self.assertIn("PkgA/0.2@user/channel", client.out)
        self.assertNotIn("PkgA/0.1@user/channel", client.out)

        # Locked install will use PkgA/0.1
        # To use the stored graph_info.json, it has to be explicit in "--install-folder"
        client.run("install . -g=cmake --lockfile")
        self._check_lock("PkgB/0.1@")

        self.assertIn("PkgA/0.1@user/channel", client.out)
        self.assertNotIn("PkgA/0.2@user/channel", client.out)
        cmake = client.load("conanbuildinfo.cmake")
        self.assertIn("PkgA/0.1/user/channel", cmake)
        self.assertNotIn("PkgA/0.2/user/channel", cmake)

        # Info also works
        client.run("info . --lockfile")
        self.assertIn("PkgA/0.1@user/channel", client.out)
        self.assertNotIn("PkgA/0.2/user/channel", client.out)

    def install_ref_lock_test(self):
        client = self.client
        client.run("install PkgA/[>=0.1]@user/channel -if=tmp")
        self.assertIn("PkgA/0.2@user/channel: Already installed!", client.out)
        self.assertNotIn("PkgA/0.1@user/channel", client.out)
        # Explicit one
        client.run("install PkgA/0.1@user/channel --install-folder=.")
        self.assertIn("PkgA/0.1@user/channel: Already installed!", client.out)
        self.assertNotIn("PkgA/0.2@user/channel", client.out)
        # Range locked one
        client.run("install PkgA/[>=0.1]@user/channel --lockfile")
        self.assertIn("PkgA/0.1@user/channel: Already installed!", client.out)
        self.assertNotIn("PkgA/0.2@user/channel", client.out)

    def export_lock_test(self):
        # locking a version range at export
        self.client.run("export . user/channel --lockfile")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.pkg_b_revision)

    def create_lock_test(self):
        # Create is also possible
        client = self.client
        client.run("create . PkgB/0.1@user/channel --lockfile")
        self.assertIn("PkgA/0.1@user/channel", client.out)
        self.assertNotIn("PkgA/0.2/user/channel", client.out)
        self._check_lock("PkgB/0.1@user/channel#%s" % self.pkg_b_revision,
                         self.pkg_b_package_revision)

    def create_test_lock_test(self):
        # Create is also possible
        client = self.client
        test_conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Test(ConanFile):
                def test(self):
                    pass
            """)
        client.save({"conanfile.py": str(self.consumer),
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . PkgB/0.1@user/channel --lockfile")
        self.assertIn("PkgA/0.1@user/channel", client.out)
        self.assertNotIn("PkgA/0.2/user/channel", client.out)
        self._check_lock("PkgB/0.1@user/channel#%s" % self.pkg_b_revision,
                         self.pkg_b_package_revision)

    def export_pkg_test(self):
        client = self.client
        client.run("export-pkg . PkgB/0.1@user/channel --lockfile")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.pkg_b_revision,
                         self.pkg_b_package_revision)

        # Same, but modifying also PkgB Recipe
        client.save({"conanfile.py": str(self.consumer) + "\n#comment"})
        client.run("export-pkg . PkgB/0.1@user/channel --lockfile --force")
        self._check_lock("PkgB/0.1@user/channel#%s" % self.modified_pkg_b_revision,
                         self.modified_pkg_b_package_revision)


class GraphLockBuildRequireVersionRangeTest(GraphLockVersionRangeTest):
    consumer = GenConanfile().with_name("PkgB").with_version("0.1")\
                             .with_build_require_plain("PkgA/[>=0.1]@user/channel")
    pkg_b_revision = "b6f49e5ba6dd3d64af09a2f288e71330"
    pkg_b_id = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
    pkg_b_package_revision = "#33a5634bbd9ec26b369d3900d91ea9a0"
    modified_pkg_b_revision = "62a38c702f14cb9de952bb22b40d6ecc"
    modified_pkg_b_package_revision = "#b7850e289326d594fbc10088d55f5259"


class GraphLockVersionRangeInfoTest(GraphLockVersionRangeTest):
    graph_lock_command = "info . --install-folder=."


class GraphLockVersionRangeGraphLockTest(GraphLockVersionRangeTest):
    graph_lock_command = "graph lock ."


class GraphLockRevisionTest(unittest.TestCase):
    pkg_b_revision = "9b64caa2465f7660e6f613b7e87f0cd7"
    pkg_b_id = "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5"
    pkg_b_package_revision = "#2ec4fb334e1b4f3fd0a6f66605066ac7"

    def setUp(self):
        test_server = TestServer(users={"user": "user"})
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("user", "user")]})
        # Important to activate revisions
        client.run("config set general.revisions_enabled=True")
        self.client = client
        client.save({"conanfile.py": GenConanfile().with_name("PkgA").with_version("0.1")})
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
        client.run("install .")

        self._check_lock("PkgB/0.1@")

        # If we create a new PkgA revision, for example adding info
        client.save({"conanfile.py": GenConanfile().with_name("PkgA").with_version("0.1")
                                        .with_package_info(cpp_info={"libs": ["mylibPkgA0.1lib"]},
                                                           env_info={"MYENV": ["myenvPkgA0.1env"]})})

        client.run("create . PkgA/0.1@user/channel")
        client.save({"conanfile.py": str(consumer)})

    def _check_lock(self, ref_b, rev_b=""):
        lock_file = load(os.path.join(self.client.current_folder, LOCKFILE))
        lock_file_json = json.loads(lock_file)
        self.assertEqual(2, len(lock_file_json["graph_lock"]["nodes"]))
        self.assertIn("PkgA/0.1@user/channel#fa090239f8ba41ad559f8e934494ee2a:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#0d561e10e25511b9bfa339d06360d7c1",
                      lock_file)
        self.assertIn('"%s:%s%s"' % (repr(ConanFileReference.loads(ref_b)),
                                     self.pkg_b_id, rev_b), lock_file)

    def install_info_lock_test(self):
        # Normal install will use it (use install-folder to not change graph-info)
        client = self.client
        client.run("install . -if=tmp")  # Output graph_info to temporary
        client.run("build . -if=tmp")
        self.assertIn("conanfile.py (PkgB/0.1): BUILD DEP LIBS: mylibPkgA0.1lib!!",
                      client.out)

        # Locked install will use PkgA/0.1
        # This is a bit weird, that is necessary to force the --update the get the rigth revision
        client.run("install . -g=cmake --lockfile --update")
        self._check_lock("PkgB/0.1@")
        client.run("build .")
        self.assertIn("conanfile.py (PkgB/0.1): BUILD DEP LIBS: !!", client.out)

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


class GraphLockPythonRequiresTest(unittest.TestCase):

    def setUp(self):
        client = TestClient()
        self.client = client
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            var = 42
            class Pkg(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . Tool/0.1@user/channel")

        # Use a consumer with a version range
        consumer = textwrap.dedent("""
            from conans import ConanFile, python_requires
            dep = python_requires("Tool/[>=0.1]@user/channel")

            class Pkg(ConanFile):
                name = "Pkg"
                def configure(self):
                    self.output.info("CONFIGURE VAR=%s" % dep.var)
                def build(self):
                    self.output.info("BUILD VAR=%s" % dep.var)
            """)
        client.save({"conanfile.py": consumer})
        client.run("install .")
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertIn("conanfile.py (Pkg/None): CONFIGURE VAR=42", client.out)
        self._check_lock("Pkg/None@")

        client.run("build .")
        self.assertIn("conanfile.py (Pkg/None): CONFIGURE VAR=42", client.out)
        self.assertIn("conanfile.py (Pkg/None): BUILD VAR=42", client.out)

        # If we create a new Tool version
        client.save({"conanfile.py": conanfile.replace("42", "111")})
        client.run("export . Tool/0.2@user/channel")
        client.save({"conanfile.py": consumer})

    def _check_lock(self, ref_b):
        ref_b = repr(ConanFileReference.loads(ref_b, validate=False))
        lock_file = load(os.path.join(self.client.current_folder, LOCKFILE))
        self.assertIn("Tool/0.1@user/channel", lock_file)
        self.assertNotIn("Tool/0.2@user/channel", lock_file)
        lock_file_json = json.loads(lock_file)
        self.assertEqual(1, len(lock_file_json["graph_lock"]["nodes"]))
        self.assertIn("%s:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9" % ref_b,
                      lock_file)
        self.assertIn('"Tool/0.1@user/channel#ac4036130c39cab7715b1402e8c211d3"', lock_file)

    def install_info_test(self):
        client = self.client
        # Make sure to use temporary if to not change graph_info.json
        client.run("install . -if=tmp")
        self.assertIn("Tool/0.2@user/channel", client.out)
        client.run("build . -if=tmp")
        self.assertIn("conanfile.py (Pkg/None): CONFIGURE VAR=111", client.out)
        self.assertIn("conanfile.py (Pkg/None): BUILD VAR=111", client.out)

        client.run("install . --lockfile")
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertNotIn("Tool/0.2@user/channel", client.out)
        self._check_lock("Pkg/None@")
        client.run("build .")
        self.assertIn("conanfile.py (Pkg/None): CONFIGURE VAR=42", client.out)
        self.assertIn("conanfile.py (Pkg/None): BUILD VAR=42", client.out)

        client.run("package .")
        self.assertIn("conanfile.py (Pkg/None): CONFIGURE VAR=42", client.out)

        client.run("info . --lockfile")
        self.assertIn("conanfile.py (Pkg/None): CONFIGURE VAR=42", client.out)

    def create_test(self):
        client = self.client
        client.run("create . Pkg/0.1@user/channel --lockfile")
        self.assertIn("Pkg/0.1@user/channel: CONFIGURE VAR=42", client.out)
        self.assertIn("Pkg/0.1@user/channel: BUILD VAR=42", client.out)
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertNotIn("Tool/0.2@user/channel", client.out)
        self._check_lock("Pkg/0.1@user/channel#332c2615c2ff9f78fc40682e733e5aa5")

    def export_pkg_test(self):
        client = self.client
        client.run("export-pkg . Pkg/0.1@user/channel --install-folder=.  --lockfile")
        self.assertIn("Pkg/0.1@user/channel: CONFIGURE VAR=42", client.out)
        self._check_lock("Pkg/0.1@user/channel#332c2615c2ff9f78fc40682e733e5aa5")


class GraphLockWarningsTestCase(unittest.TestCase):

    def test_override(self):
        client = TestClient()
        harfbuzz_ref = ConanFileReference.loads("harfbuzz/1.0")
        ffmpeg_ref = ConanFileReference.loads("ffmpeg/1.0")
        client.save({"harfbuzz.py": GenConanfile().with_name("harfbuzz").with_version("1.0"),
                     "ffmpeg.py": GenConanfile().with_name("ffmpeg").with_version("1.0")
                                                .with_requirement_plain("harfbuzz/[>=1.0]"),
                     "meta.py": GenConanfile().with_name("meta").with_version("1.0")
                                              .with_requirement(ffmpeg_ref)
                                              .with_requirement(harfbuzz_ref)
                     })
        client.run("export harfbuzz.py")
        client.run("export ffmpeg.py")
        client.run("export meta.py")

        # Building the graphlock we get the message
        client.run("graph lock meta.py")
        self.assertIn("WARN: ffmpeg/1.0: requirement harfbuzz/[>=1.0] overridden by meta/1.0"
                      " to harfbuzz/1.0", client.out)

        # Using the graphlock there is no warning message
        client.run("graph build-order conan.lock")
        self.assertNotIn("overridden", client.out)
        self.assertNotIn("WARN", client.out)
