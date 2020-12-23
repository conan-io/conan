import json
import textwrap
import unittest

import pytest

from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.env_reader import get_env


class LockRecipeTest(unittest.TestCase):

    def test_error_pass_base(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . pkg/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1")})
        client.run("lock create conanfile.py --base --lockfile-out=conan.lock")
        client.run("install . --lockfile=conan.lock", assert_error=True)
        self.assertIn("Lockfiles with --base do not contain profile information, "
                      "cannot be used. Create a full lockfile", client.out)

    def test_lock_recipe(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_setting("os")})
        client.run("create . pkg/0.1@ -s os=Windows")
        self.assertIn("pkg/0.1:3475bd55b91ae904ac96fde0f106a136ab951a5e - Build", client.out)
        self.assertIn("pkg/0.1: Created package revision d0f0357277b3417d3984b5a9a85bbab6",
                      client.out)
        client.run("create . pkg/0.1@ -s os=Linux")
        self.assertIn("pkg/0.1:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31 - Build", client.out)
        self.assertIn("pkg/0.1: Created package revision 9e99cfd92d0d7df79d687b01512ce844",
                      client.out)

        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1")})
        client.run("lock create conanfile.py --base --lockfile-out=base.lock")
        lock = json.loads(client.load("base.lock"))
        self.assertEqual(2, len(lock["graph_lock"]["nodes"]))
        pkg_node = lock["graph_lock"]["nodes"]["1"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(pkg_node["ref"], "pkg/0.1#f096d7d54098b7ad7012f9435d9c33f3")
        else:
            self.assertEqual(pkg_node["ref"], "pkg/0.1")
        client.run("lock create conanfile.py -s os=Linux "
                   "--lockfile-out=linux.lock --lockfile=base.lock")
        lock = json.loads(client.load("linux.lock"))
        pkg_node = lock["graph_lock"]["nodes"]["1"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(pkg_node["ref"], "pkg/0.1#f096d7d54098b7ad7012f9435d9c33f3")
            self.assertEqual(pkg_node["package_id"], "cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31")
            self.assertEqual(pkg_node["prev"], "9e99cfd92d0d7df79d687b01512ce844")
        else:
            self.assertEqual(pkg_node["ref"], "pkg/0.1")
            self.assertEqual(pkg_node["package_id"], "cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31")
            self.assertEqual(pkg_node["prev"], "0")
        self.assertEqual(pkg_node["options"], "")
        self.assertIsNone(pkg_node.get("modified"))

        client.run("lock create conanfile.py -s os=Windows "
                   "--lockfile-out=windows.lock --lockfile=base.lock")
        lock = json.loads(client.load("windows.lock"))
        pkg_node = lock["graph_lock"]["nodes"]["1"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(pkg_node["ref"], "pkg/0.1#f096d7d54098b7ad7012f9435d9c33f3")
            self.assertEqual(pkg_node["package_id"], "3475bd55b91ae904ac96fde0f106a136ab951a5e")
            self.assertEqual(pkg_node["prev"], "d0f0357277b3417d3984b5a9a85bbab6")
        else:
            self.assertEqual(pkg_node["ref"], "pkg/0.1")
            self.assertEqual(pkg_node["package_id"], "3475bd55b91ae904ac96fde0f106a136ab951a5e")
            self.assertEqual(pkg_node["prev"], "0")
        self.assertEqual(pkg_node["options"], "")

        # Now it is possible to obtain the base one again from the full ones
        client.run("lock create conanfile.py --base "
                   "--lockfile-out=windows_base.lock --lockfile=windows.lock")
        self.assertEqual(client.load("windows_base.lock"), client.load("base.lock"))
        # Now it is possible to obtain the base one again from the full ones
        client.run("lock create conanfile.py --base "
                   "--lockfile-out=linux_base.lock --lockfile=linux.lock")
        self.assertEqual(client.load("linux_base.lock"), client.load("base.lock"))

    def test_lock_recipe_from_partial(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=base.lock --base")
        client.run("lock create --reference=LibB/1.0 --lockfile=base.lock --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        client.save({"conanfile.py": GenConanfile().with_require("LibB/1.0")})

        for lock in ("base.lock", "libb.lock"):
            client.run("lock create conanfile.py --name=LibC --version=1.0 --lockfile=%s "
                       "--lockfile-out=full.lock --base" % lock)
            self.assertIn("LibA/1.0 from local cache - Cache", client.out)

            lock = json.loads(client.load("full.lock"))
            for id_, ref, rrev in ("1", "LibB/1.0", "6e5c7369c3d3f7a7a5a60ddec16a941f"), \
                                  ("2", "LibA/1.0", "f3367e0e7d170aa12abccb175fee5f97"):
                pkg_node = lock["graph_lock"]["nodes"][id_]
                if client.cache.config.revisions_enabled:
                    self.assertEqual(pkg_node["ref"], "%s#%s" % (ref, rrev))
                else:
                    self.assertEqual(pkg_node["ref"], ref)
                self.assertIsNone(pkg_node.get("package_id"))
                self.assertIsNone(pkg_node.get("prev"))
                self.assertIsNone(pkg_node.get("options"))

    def test_conditional_lock_recipe(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . common/0.1@")
        client.run("create . win/0.1@")
        client.run("create . linux/0.1@")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "os"
                requires = "common/0.1"
                def requirements(self):
                    if self.settings.os == "Windows":
                        self.requires("win/0.1")
                    else:
                        self.requires("linux/0.1")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("lock create conanfile.py --base -s os=Windows --lockfile-out=conan.lock")
        lock = json.loads(client.load("conan.lock"))
        self.assertEqual(3, len(lock["graph_lock"]["nodes"]))
        common = lock["graph_lock"]["nodes"]["1"]
        win = lock["graph_lock"]["nodes"]["2"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(common["ref"], "common/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(win["ref"], "win/0.1#f3367e0e7d170aa12abccb175fee5f97")
        else:
            self.assertEqual(common["ref"], "common/0.1")
            self.assertEqual(win["ref"], "win/0.1")
        self.assertIsNone(common.get("package_id"))
        self.assertIsNone(common.get("prev"))
        self.assertIsNone(common.get("options"))
        self.assertIsNone(win.get("package_id"))
        self.assertIsNone(win.get("prev"))
        self.assertIsNone(win.get("options"))

        client.run("lock create conanfile.py -s os=Linux "
                   "--lockfile-out=linux.lock --lockfile=conan.lock")
        lock = json.loads(client.load("linux.lock"))
        self.assertEqual(3, len(lock["graph_lock"]["nodes"]))
        common = lock["graph_lock"]["nodes"]["1"]
        linux = lock["graph_lock"]["nodes"]["3"]
        self.assertNotIn("2", lock["graph_lock"]["nodes"])
        if client.cache.config.revisions_enabled:
            self.assertEqual(common["ref"], "common/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(common["prev"], "83c38d3b4e5f1b8450434436eec31b00")
            self.assertEqual(linux["ref"], "linux/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(linux["prev"], "83c38d3b4e5f1b8450434436eec31b00")
        else:
            self.assertEqual(common["ref"], "common/0.1")
            self.assertEqual(common["prev"], "0")
            self.assertEqual(linux["ref"], "linux/0.1")
            self.assertEqual(linux["prev"], "0")
        self.assertEqual(common["options"], "")
        self.assertEqual(common["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(linux["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(linux["options"], "")

        client.run("lock create conanfile.py -s os=Windows "
                   "--lockfile-out=windows.lock --lockfile=conan.lock")
        lock = json.loads(client.load("windows.lock"))
        self.assertEqual(3, len(lock["graph_lock"]["nodes"]))
        common = lock["graph_lock"]["nodes"]["1"]
        win = lock["graph_lock"]["nodes"]["2"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(common["ref"], "common/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(common["prev"], "83c38d3b4e5f1b8450434436eec31b00")
            self.assertEqual(win["ref"], "win/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(win["prev"], "83c38d3b4e5f1b8450434436eec31b00")
        else:
            self.assertEqual(common["ref"], "common/0.1")
            self.assertEqual(common["prev"], "0")
            self.assertEqual(win["ref"], "win/0.1")
            self.assertEqual(win["prev"], "0")
        self.assertEqual(common["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(common["options"], "")
        self.assertEqual(win["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(win["options"], "")

    @pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
    def test_lose_rrev(self):
        # https://github.com/conan-io/conan/issues/7595
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_package_mode")
        files = {
            "pkga/conanfile.py": GenConanfile(),
            "pkgb/conanfile.py": GenConanfile().with_require("liba/[*]"),
        }
        client.save(files)

        client.run("create pkga liba/0.1@")

        client.run("lock create pkgb/conanfile.py --name=libb --version=0.1 "
                   "--lockfile-out=base.lock --base")

        client.run("export pkgb libb/0.1@ --lockfile=base.lock --lockfile-out=libb_base.lock")
        client.run("lock create --reference=libb/0.1@ --lockfile=libb_base.lock "
                   "--lockfile-out=libb_release.lock --build=missing")
        libb_release = client.load("libb_release.lock")
        self.assertIn('"ref": "libb/0.1#c2a641589d4b617387124f011905a97b"', libb_release)

        client.run("create pkgb libb/0.1@ --lockfile=libb_release.lock")
        self.assertIn("libb/0.1: Created package", client.out)

    @pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
    def test_missing_configuration(self):
        client = TestClient()
        client.run("config set general.default_package_id_mode=package_revision_mode")
        client.save({"conanfile.py": GenConanfile().with_setting("os")})
        client.run("create . liba/0.1@ -s os=Windows")
        self.assertIn("liba/0.1:3475bd55b91ae904ac96fde0f106a136ab951a5e - Build", client.out)
        self.assertIn("liba/0.1: Created package revision d0f0357277b3417d3984b5a9a85bbab6",
                      client.out)

        client.save({"conanfile.py": GenConanfile().with_require("liba/0.1")})
        client.run("export . libb/0.1@")
        client.run("lock create --reference=libb/0.1 --base --lockfile-out=conan.lock -s os=Windows")

        client.run("lock create --reference=libb/0.1 -s os=Windows "
                   "--lockfile-out=windows.lock --lockfile=conan.lock "
                   "--build=libb/0.1 --build=missing")
        self.assertIn("libb/0.1:d9a360017881eddb68099b9a3573a4c0d39f3df5 - Build", client.out)

        client.run("lock create --reference=libb/0.1 -s os=Linux "
                   "--lockfile-out=linux.lock --lockfile=conan.lock "
                   "--build=libb/0.1 --build=missing")
        self.assertIn("libb/0.1:Package_ID_unknown - Unknown", client.out)

    @pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
    def test_missing_configuration_build_require(self):
        client = TestClient()
        client.run("config set general.default_package_id_mode=package_revision_mode")

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . cmake/1.0@")
        client.save({"conanfile.py": GenConanfile().with_setting("os"),
                     "myprofile": "[build_requires]\ncmake/1.0"})
        client.run("create . liba/0.1@ -s os=Windows --profile=myprofile")
        self.assertIn("liba/0.1:3475bd55b91ae904ac96fde0f106a136ab951a5e - Build", client.out)
        self.assertIn("liba/0.1: Created package revision d0f0357277b3417d3984b5a9a85bbab6",
                      client.out)

        client.save({"conanfile.py": GenConanfile().with_require("liba/0.1")})
        client.run("lock create conanfile.py --name=libb --version=0.1 --base "
                   "--lockfile-out=conan.lock --profile=myprofile -s os=Windows --build")

        client.run("export . libb/0.1@ --lockfile=conan.lock --lockfile-out=conan.lock")

        client.run("lock create --reference=libb/0.1 -s os=Windows "
                   "--lockfile-out=windows.lock --lockfile=conan.lock "
                   "--build=libb/0.1 --build=missing --profile=myprofile")
        self.assertIn("liba/0.1:3475bd55b91ae904ac96fde0f106a136ab951a5e - Cache", client.out)
        self.assertIn("libb/0.1:d9a360017881eddb68099b9a3573a4c0d39f3df5 - Build", client.out)
        self.assertIn("cmake/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)

        client.run("lock create --reference=libb/0.1 -s os=Linux "
                   "--lockfile-out=linux.lock --lockfile=conan.lock "
                   "--build=libb/0.1 --build=missing --profile=myprofile")
        self.assertNotIn("ERROR: No package matching 'libb/0.1' pattern", client.out)
        self.assertIn("liba/0.1:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31 - Build", client.out)
        self.assertIn("libb/0.1:Package_ID_unknown - Unknown", client.out)
        self.assertIn("cmake/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
