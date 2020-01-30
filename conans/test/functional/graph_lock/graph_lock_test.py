import json
import os
import textwrap
import unittest

from conans.model.graph_lock import LOCKFILE, LOCKFILE_VERSION
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TestServer, GenConanfile
from conans.util.env_reader import get_env
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
    consumer = GenConanfile().with_name("PkgB").with_version("0.1")\
                             .with_require_plain("PkgA/[>=0.1]@user/channel")
    pkg_b_revision = "180919b324d7823f2683af9381d11431"
    pkg_b_id = "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5"
    pkg_b_package_revision = "#2913f67cea630aee496fe70fd38b5b0f"

    def _check_lock(self, ref_b, rev_b=""):
        ref_b = repr(ConanFileReference.loads(ref_b))
        lock_file = self.client.load("custom.lock")
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


class ReproducibleLockfiles(unittest.TestCase):
    def reproducible_lockfile_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("PkgA").with_version("0.1")})
        client.run("create . PkgA/0.1@user/channel")

        # Use a consumer with a version range
        client.save({"conanfile.py": GenConanfile().with_name("PkgB").with_version("0.1")
                                                   .with_require_plain("PkgA/[>=0.1]@user/channel")})
        client.run("graph lock .")
        lockfile = client.load(LOCKFILE)
        client.run("graph lock .")
        lockfile2 = client.load(LOCKFILE)
        self.assertEqual(lockfile, lockfile2)

    def reproducible_lockfile_txt_test(self):
        client = TestClient()
        client.save({"conanfile.txt": ""})
        client.run("install .")
        lockfile = client.load("conan.lock")
        client.run("install .")
        lockfile2 = client.load("conan.lock")
        self.assertEqual(lockfile, lockfile2)

    def error_old_format_test(self):
        client = TestClient()
        client.save({"conanfile.txt": ""})
        client.run("install .")
        lockfile = client.load("conan.lock")
        lockfile = lockfile.replace('"0.3"', '"0.1"').replace('"0"', '"UUID"')
        client.save({"conan.lock": lockfile})
        client.run("install . --lockfile", assert_error=True)
        self.assertIn("This lockfile was created with a previous incompatible version", client.out)


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
        lock_file = self.client.load(LOCKFILE)
        lock_file_json = json.loads(lock_file)
        self.assertEqual(2, len(lock_file_json["graph_lock"]["nodes"]))
        self.assertIn("PkgA/0.1@user/channel#fa090239f8ba41ad559f8e934494ee2a:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#0d561e10e25511b9bfa339d06360d7c1",
                      lock_file)
        self.assertIn('"%s:%s%s"' % (repr(ConanFileReference.loads(ref_b)), self.pkg_b_id, rev_b),
                      lock_file)

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


class GraphLockVersionRangeNoUserChannelTest(unittest.TestCase):
    # This is exactly the same as above, but not using user/channel in packages
    # https://github.com/conan-io/conan/issues/5873
    consumer = GenConanfile().with_name("PkgB").with_version("0.1")\
                             .with_require_plain("PkgA/[>=0.1]")
    pkg_b_revision = "afa95143c0c11c46ad57670e1e0a0aa0"
    pkg_b_id = "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5"
    pkg_b_package_revision = "#f97ac3d1bee62d55a35085dd42fa847a"
    modified_pkg_b_revision = "3bb0f77004b0afde1620c714630aa515"
    modified_pkg_b_package_revision = "#7f92394bbc66cc7f9d403e764b88bac0"
    graph_lock_command = "install ."

    def setUp(self):
        client = TestClient()
        self.client = client
        client.save({"conanfile.py": GenConanfile().with_name("PkgA").with_version("0.1")})
        client.run("create .")

        # Use a consumer with a version range
        client.save({"conanfile.py": str(self.consumer)})
        client.run(self.graph_lock_command)

        self._check_lock("PkgB/0.1@")

        # If we create a new PkgA version
        client.save({"conanfile.py": GenConanfile().with_name("PkgA").with_version("0.2")})
        client.run("create .")
        client.save({"conanfile.py": str(self.consumer)})

    def _check_lock(self, ref_b, rev_b=""):
        lock_file = load(os.path.join(self.client.current_folder, LOCKFILE))
        lock_file_json = json.loads(lock_file)
        self.assertEqual(2, len(lock_file_json["graph_lock"]["nodes"]))
        self.assertIn("PkgA/0.1#fa090239f8ba41ad559f8e934494ee2a:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#0d561e10e25511b9bfa339d06360d7c1",
                      lock_file)
        self.assertIn('"%s:%s%s"' % (repr(ConanFileReference.loads(ref_b)), self.pkg_b_id, rev_b),
                      lock_file)

    def install_info_lock_test(self):
        # Normal install will use it (use install-folder to not change graph-info)
        client = self.client
        client.run("install . -if=tmp")  # Output graph_info to temporary
        self.assertIn("PkgA/0.2", client.out)
        self.assertNotIn("PkgA/0.1", client.out)

        # Locked install will use PkgA/0.1
        # To use the stored graph_info.json, it has to be explicit in "--install-folder"
        client.run("install . -g=cmake --lockfile")
        self._check_lock("PkgB/0.1@")

        self.assertIn("PkgA/0.1", client.out)
        self.assertNotIn("PkgA/0.2", client.out)
        cmake = client.load("conanbuildinfo.cmake")
        self.assertIn("PkgA/0.1/_/_", cmake)
        self.assertNotIn("PkgA/0.2/_/_", cmake)

        # Info also works
        client.run("info . --lockfile")
        self.assertIn("PkgA/0.1", client.out)
        self.assertNotIn("PkgA/0.2", client.out)

    def install_ref_lock_test(self):
        client = self.client
        client.run("install PkgA/[>=0.1]@ -if=tmp")
        self.assertIn("PkgA/0.2: Already installed!", client.out)
        self.assertNotIn("PkgA/0.1", client.out)
        # Explicit one
        client.run("install PkgA/0.1@ --install-folder=.")
        self.assertIn("PkgA/0.1: Already installed!", client.out)
        self.assertNotIn("PkgA/0.2", client.out)
        # Range locked one
        client.run("install PkgA/[>=0.1]@ --lockfile")
        self.assertIn("PkgA/0.1: Already installed!", client.out)
        self.assertNotIn("PkgA/0.2", client.out)

    def export_lock_test(self):
        # locking a version range at export
        self.client.run("export . --lockfile")
        self._check_lock("PkgB/0.1#%s" % self.pkg_b_revision)

    def create_lock_test(self):
        # Create is also possible
        client = self.client
        client.run("create . PkgB/0.1@ --lockfile")
        self.assertIn("PkgA/0.1", client.out)
        self.assertNotIn("PkgA/0.2", client.out)
        self._check_lock("PkgB/0.1#%s" % self.pkg_b_revision, self.pkg_b_package_revision)

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
        client.run("create . PkgB/0.1@ --lockfile")
        self.assertIn("PkgA/0.1", client.out)
        self.assertNotIn("PkgA/0.2", client.out)
        self._check_lock("PkgB/0.1#%s" % self.pkg_b_revision,
                         self.pkg_b_package_revision)

    def export_pkg_test(self):
        client = self.client
        client.run("export-pkg . PkgB/0.1@ --lockfile")
        self._check_lock("PkgB/0.1#%s" % self.pkg_b_revision,
                         self.pkg_b_package_revision)

        # Same, but modifying also PkgB Recipe
        client.save({"conanfile.py": str(self.consumer) + "\n#comment"})
        client.run("export-pkg . PkgB/0.1@ --lockfile --force")
        self._check_lock("PkgB/0.1@#%s" % self.modified_pkg_b_revision,
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


@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
class GraphLockRevisionTest(unittest.TestCase):
    pkg_b_revision = "9b64caa2465f7660e6f613b7e87f0cd7"
    pkg_b_id = "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5"
    pkg_b_package_revision = "#2ec4fb334e1b4f3fd0a6f66605066ac7"

    def setUp(self):
        test_server = TestServer(users={"user": "user"})
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("user", "user")]})
        # Important to activate revisions
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
        pkga = GenConanfile().with_name("PkgA").with_version("0.1")
        pkga.with_package_info(cpp_info={"libs": ["mylibPkgA0.1lib"]},
                               env_info={"MYENV": ["myenvPkgA0.1env"]})
        client.save({"conanfile.py": pkga})

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


class GraphLockConsumerBuildOrderTest(unittest.TestCase):

    def consumer_build_order_local_test(self):
        # https://github.com/conan-io/conan/issues/5727
        client = TestClient(default_server_user=True)

        consumer_ref = ConanFileReference("test4", "0.1", None, None, None)
        consumer = GenConanfile().with_name(consumer_ref.name).with_version(consumer_ref.version)

        client.save({"conanfile.py": consumer})
        client.run("graph lock .")
        client.run("graph build-order conan.lock --build=missing")
        self.assertIn("[]", client.out)

    def build_order_build_requires_test(self):
        # https://github.com/conan-io/conan/issues/5474
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . CA/1.0@user/channel")
        client.save({"conanfile.py": GenConanfile().with_build_require_plain("CA/1.0@user/channel")})
        client.run("create . CB/1.0@user/channel")

        consumer = textwrap.dedent("""
            [requires]
            CA/1.0@user/channel
            CB/1.0@user/channel
        """)
        client.save({"conanfile.txt": consumer})
        client.run("graph lock conanfile.txt --build")
        client.run("graph build-order . --build --json=bo.json")
        jsonbo = json.loads(client.load("bo.json"))
        level0 = jsonbo[0]
        ca = level0[0]
        self.assertEqual("CA/1.0@user/channel#f3367e0e7d170aa12abccb175fee5f97"
                         ":5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", ca[1])
        level1 = jsonbo[1]
        cb = level1[0]
        self.assertEqual("CB/1.0@user/channel#29352c82c9c6b7d1be85524ef607f77f"
                         ":5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", cb[1])

    def consumer_build_order_test(self):
        # https://github.com/conan-io/conan/issues/5727
        client = TestClient(default_server_user=True)

        consumer_ref = ConanFileReference("test4", "0.1", None, None, None)
        consumer = GenConanfile().with_name(consumer_ref.name).with_version(consumer_ref.version)

        client.save({"conanfile.py": consumer})
        client.run("export .")
        client.run("graph lock test4/0.1@")
        client.run("graph build-order conan.lock --build=missing")
        self.assertIn("test4/0.1", client.out)

    def package_revision_mode_build_order_test(self):
        # https://github.com/conan-io/conan/issues/6232
        client = TestClient()
        client.run("config set general.default_package_id_mode=package_revision_mode")
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . libb/0.1@")
        client.run("export . libc/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("libc/0.1")})
        client.run("export . liba/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("liba/0.1")
                                                   .with_require_plain("libb/0.1")})
        client.run("export . app/0.1@")

        client.run("graph lock app/0.1@ --build=missing")
        client.run("graph build-order . --build=missing --json=bo.json")
        self.assertIn("app/0.1:Package_ID_unknown - Unknown", client.out)
        self.assertIn("liba/0.1:Package_ID_unknown - Unknown", client.out)
        self.assertIn("libb/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        self.assertIn("libc/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        bo = client.load("bo.json")
        build_order = json.loads(bo)
        expected = [
            # First level
            [['3',
              'libc/0.1#f3367e0e7d170aa12abccb175fee5f97:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9']],
            # second level
            [['2', 'liba/0.1#7086607aa6efbad8e2527748e3ee8237:Package_ID_unknown'],
             ['4',
              'libb/0.1#f3367e0e7d170aa12abccb175fee5f97:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9']],
            # last level to build
            [['1', 'app/0.1#7742ee9e2f19af4f9ed7619f231ca871:Package_ID_unknown']]
        ]
        self.assertEqual(build_order, expected)


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


class GraphLockBuildRequireErrorTestCase(unittest.TestCase):

    def test(self):
        # https://github.com/conan-io/conan/issues/5807
        client = TestClient()
        client.save({"zlib.py": GenConanfile(),
                     "harfbuzz.py": GenConanfile().with_require_plain("fontconfig/1.0"),
                     "fontconfig.py": GenConanfile(),
                     "ffmpeg.py": GenConanfile().with_build_require_plain("fontconfig/1.0")
                                                .with_build_require_plain("harfbuzz/1.0"),
                     "variant.py": GenConanfile().with_require_plain("ffmpeg/1.0")
                                                 .with_require_plain("fontconfig/1.0")
                                                 .with_require_plain("harfbuzz/1.0")
                                                 .with_require_plain("zlib/1.0")
                     })
        client.run("export zlib.py zlib/1.0@")
        client.run("export fontconfig.py fontconfig/1.0@")
        client.run("export harfbuzz.py harfbuzz/1.0@")
        client.run("export ffmpeg.py ffmpeg/1.0@")

        # Building the graphlock we get the message
        client.run("graph lock variant.py")
        fmpe = "ffmpeg/1.0#5522e93e2abfbd455e6211fe4d0531a2:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        font = "fontconfig/1.0#f3367e0e7d170aa12abccb175fee5f97:"\
               "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        harf = "harfbuzz/1.0#3172f5e84120f235f75f8dd90fdef84f:"\
               "ea61889683885a5517800e8ebb09547d1d10447a"
        zlib = "zlib/1.0#f3367e0e7d170aa12abccb175fee5f97:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        lock = json.loads(client.load("conan.lock"))
        nodes = lock["graph_lock"]["nodes"]
        self.assertEqual(5, len(nodes))
        self.assertEqual(fmpe, nodes["1"]["pref"])
        self.assertEqual(font, nodes["2"]["pref"])
        self.assertEqual(harf, nodes["3"]["pref"])
        self.assertEqual(zlib, nodes["4"]["pref"])

        # Using the graphlock there is no warning message
        client.run("graph build-order . --build cascade --build outdated", assert_error=True)
        self.assertIn("ERROR: 'fontconfig' cannot be found in lockfile for this package", client.out)
        self.assertIn("Make sure it was locked ", client.out)


class GraphLockModifyConanfileTestCase(unittest.TestCase):

    def test(self):
        # https://github.com/conan-io/conan/issues/5807
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . zlib/1.0@")

        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": GenConanfile()})
        client2.run("graph lock .")
        client2.save({"conanfile.py": GenConanfile().with_require_plain("zlib/1.0")})
        client2.run("install . --lockfile", assert_error=True)
        self.assertIn("ERROR: 'zlib' cannot be found in lockfile for this package", client2.out)
        self.assertIn("If it is a new requirement, you need to create a new lockile", client2.out)


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
