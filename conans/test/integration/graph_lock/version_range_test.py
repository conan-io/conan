import json
import unittest

from conans.model.graph_lock import LOCKFILE
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.env_reader import get_env


class GraphLockVersionRangeTest(unittest.TestCase):
    user_channel = "user/channel"
    consumer = GenConanfile("PkgB", "0.1").with_require("PkgA/[>=0.1]@user/channel")
    upload = False
    if get_env("TESTING_REVISIONS_ENABLED", False):
        ref_a = "PkgA/0.1@user/channel#fa090239f8ba41ad559f8e934494ee2a"
        pkg_id_a = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        prev_a = "0d561e10e25511b9bfa339d06360d7c1"
        ref_b = "PkgB/0.1@user/channel"
        rrev_b = "e8cabe5f1c737bcb8223b667f071842d"
        pkg_id_b = "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5"
        prev_b = "97d1695f4e456433cc5a1dfa14655a0f"
    else:
        ref_a = "PkgA/0.1@user/channel"
        pkg_id_a = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        prev_a = "0"
        ref_b = "PkgB/0.1@user/channel"
        rrev_b = "0"
        pkg_id_b = "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5"
        prev_b = "0"

    def setUp(self):
        client = TestClient(default_server_user=True)
        self.client = client
        client.save({"conanfile.py": GenConanfile("PkgA", "0.1")})
        client.run("create . %s" % self.user_channel)
        if self.upload:
            client.run("upload PkgA/0.1* --all --confirm")
            client.run("remove * -f")

        # Use a consumer with a version range
        client.save({"conanfile.py": self.consumer})
        if self.user_channel:
            user, channel = self.user_channel.split("/")
            client.run("lock create conanfile.py  --lockfile-out=conan.lock "
                       "--user=%s --channel=%s" % (user, channel))
        else:
            client.run("lock create conanfile.py --lockfile-out=conan.lock")

        self._check_lock()

        # If we create a new PkgA version
        client.save({"conanfile.py": GenConanfile("PkgA", "0.2")})
        client.run("create . %s" % self.user_channel)
        if self.upload:
            client.run("upload PkgA/0.2* --all --confirm")
            client.run("remove * -f")
        client.save({"conanfile.py": self.consumer})

    def _check_lock(self, rrev_b=None, prev_b=None, package_id_b=None):
        lock_file = self.client.load(LOCKFILE)
        lock_file_json = json.loads(lock_file)
        nodes = lock_file_json["graph_lock"]["nodes"]
        pkg_a = nodes["1"]

        self.assertEqual(pkg_a["ref"], self.ref_a)
        self.assertEqual(pkg_a["package_id"],  self.pkg_id_a)
        self.assertEqual(pkg_a["prev"], self.prev_a)

        pkg_b = nodes["0"]
        ref_b = self.ref_b if (rrev_b is None or rrev_b == "0") else "%s#%s" % (self.ref_b, rrev_b)
        self.assertEqual(pkg_b["ref"], ref_b)
        self.assertEqual(pkg_b.get("package_id"), package_id_b)
        self.assertEqual(pkg_b.get("prev"), prev_b)

    def test_install_lock(self):
        # Normal install will use it (use install-folder to not change graph-info)
        client = self.client
        client.run("install . -if=tmp")  # Output graph_info to temporary
        self.assertIn("PkgA/0.2", client.out)
        self.assertNotIn("PkgA/0.1", client.out)

        # Locked install will use PkgA/0.1
        # To use the stored graph_info.json, it has to be explicit in "--install-folder"
        client.run("install . -g=cmake --lockfile=conan.lock")
        self._check_lock()

        self.assertIn("PkgA/0.1", client.out)
        self.assertNotIn("PkgA/0.2", client.out)
        cmake = client.load("conanbuildinfo.cmake")
        self.assertIn("PkgA/0.1", cmake)
        self.assertNotIn("PkgA/0.2", cmake)

    def test_info_lock(self):
        client = self.client
        client.run("info . --lockfile=conan.lock")
        self.assertIn("PkgA/0.1", client.out)
        self.assertNotIn("PkgA/0.2", client.out)
        self._check_lock()

    def test_install_ref_lock(self):
        client = self.client
        # Make sure not using lockfile, will get PkgA/0.2
        client.run("install PkgA/[>=0.1]@%s -if=tmp" % self.user_channel)
        user_channel = "@%s" % self.user_channel if self.user_channel else ""
        if self.upload:
            self.assertIn("PkgA/0.2%s: Downloaded package" % user_channel, client.out)
        else:
            self.assertIn("PkgA/0.2%s: Already installed!" % user_channel, client.out)
        self.assertNotIn("PkgA/0.1", client.out)
        # Not using lockfile, even if one in the folder
        client.run("install PkgA/0.1@%s --install-folder=." % self.user_channel)
        if self.upload:
            self.assertIn("PkgA/0.1%s: Downloaded package" % user_channel, client.out)
        else:
            self.assertIn("PkgA/0.1%s: Already installed!" % user_channel, client.out)
        self.assertNotIn("PkgA/0.2", client.out)
        client.run("install PkgA/0.2@%s --install-folder=." % self.user_channel)
        self.assertIn("PkgA/0.2%s: Already installed!" % user_channel, client.out)
        self.assertNotIn("PkgA/0.1", client.out)
        self._check_lock()
        # Range locked one, outside of range, should raise
        client.run("install PkgA/[>=0.3]@%s --lockfile=conan.lock" % self.user_channel,
                   assert_error=True)
        self.assertIn("ERROR: Version ranges not allowed in 'PkgA/[>=0.3]", client.out)
        client.run("install PkgA/0.3@%s --lockfile=conan.lock" % self.user_channel,
                   assert_error=True)
        self.assertIn("Couldn't find 'PkgA/0.3", client.out)

        # inside range should be possible to find it
        client.run("install PkgA/0.1@%s --lockfile=conan.lock" % self.user_channel)
        self.assertIn("PkgA/0.1%s: Already installed!" % user_channel, client.out)
        self.assertNotIn("PkgA/0.2", client.out)
        self._check_lock()

    def test_export_lock(self):
        # locking a version range at export
        self.client.run("export . %s --lockfile=conan.lock --lockfile-out=conan.lock"
                        % self.user_channel)
        self._check_lock(self.rrev_b)

    def test_create_lock(self):
        # Create is also possible
        client = self.client
        client.run("create . PkgB/0.1@%s --lockfile=conan.lock --lockfile-out=conan.lock"
                   % self.user_channel)
        self.assertIn("PkgA/0.1", client.out)
        self.assertNotIn("PkgA/0.2", client.out)
        self._check_lock(self.rrev_b, self.prev_b, self.pkg_id_b)

    def test_create_test_lock(self):
        # Create with test_package is also possible
        client = self.client
        client.save({"test_package/conanfile.py": GenConanfile().with_test("pass")})
        client.run("create . PkgB/0.1@%s --lockfile=conan.lock  --lockfile-out=conan.lock"
                   % self.user_channel)
        self.assertIn("(test package)", client.out)
        self.assertIn("PkgA/0.1", client.out)
        self.assertNotIn("PkgA/0.2", client.out)
        self._check_lock(self.rrev_b, self.prev_b, self.pkg_id_b)

    def test_export_pkg(self):
        client = self.client
        client.run("export-pkg . PkgB/0.1@%s --lockfile=conan.lock --lockfile-out=conan.lock"
                   % self.user_channel)
        self._check_lock(self.rrev_b, self.prev_b, self.pkg_id_b)

        # Same, but modifying also PkgB Recipe
        client.save({"conanfile.py": str(self.consumer) + "\n#comment"})
        client.run("export-pkg . PkgB/0.1@%s --lockfile=conan.lock --force" % self.user_channel,
                   assert_error=True)
        self.assertIn("Attempt to modify locked PkgB/0.1", client.out)


class GraphLockVersionRangeUploadTest(GraphLockVersionRangeTest):
    upload = True


class GraphLockVersionRangeNoUserChannelTest(GraphLockVersionRangeTest):
    # This is exactly the same as above, but not using user/channel in packages
    # https://github.com/conan-io/conan/issues/5873
    user_channel = ""
    consumer = GenConanfile("PkgB", "0.1").with_require("PkgA/[>=0.1]")
    upload = False
    if get_env("TESTING_REVISIONS_ENABLED", False):
        ref_a = "PkgA/0.1#fa090239f8ba41ad559f8e934494ee2a"
        pkg_id_a = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        prev_a = "0d561e10e25511b9bfa339d06360d7c1"
        ref_b = "PkgB/0.1"
        rrev_b = "afa95143c0c11c46ad57670e1e0a0aa0"
        pkg_id_b = "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5"
        prev_b = "f97ac3d1bee62d55a35085dd42fa847a"
    else:
        ref_a = "PkgA/0.1"
        pkg_id_a = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        prev_a = "0"
        ref_b = "PkgB/0.1"
        rrev_b = "0"
        pkg_id_b = "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5"
        prev_b = "0"


class GraphLockVersionRangeNoUserChannelUploadTest(GraphLockVersionRangeNoUserChannelTest):
    upload = True


class GraphLockBuildRequireVersionRangeTest(GraphLockVersionRangeTest):
    user_channel = "user/channel"
    consumer = GenConanfile("PkgB", "0.1").with_build_requires("PkgA/[>=0.1]@user/channel")
    upload = False
    if get_env("TESTING_REVISIONS_ENABLED", False):
        ref_a = "PkgA/0.1@user/channel#fa090239f8ba41ad559f8e934494ee2a"
        pkg_id_a = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        prev_a = "0d561e10e25511b9bfa339d06360d7c1"
        ref_b = "PkgB/0.1@user/channel"
        rrev_b = "b6f49e5ba6dd3d64af09a2f288e71330"
        pkg_id_b = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        prev_b = "33a5634bbd9ec26b369d3900d91ea9a0"
    else:
        ref_a = "PkgA/0.1@user/channel"
        pkg_id_a = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        prev_a = "0"
        ref_b = "PkgB/0.1@user/channel"
        rrev_b = "0"
        pkg_id_b = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        prev_b = "0"


class GraphLockBuildRequireVersionRangeUploadTest(GraphLockBuildRequireVersionRangeTest):
    upload = True
