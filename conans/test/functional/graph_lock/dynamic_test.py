import json
import textwrap
import unittest

from conans.client.tools.env import environment_append
from conans.test.utils.tools import TestClient, GenConanfile


class GraphLockDynamicTest(unittest.TestCase):

    def test_partial_lock(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        client.save({"conanfile.py": GenConanfile().with_require("LibB/1.0")})
        client.run("create . LibC/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibC/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibC --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libc.lock")

        client.run("create . LibC/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        client.run("create . LibC/1.0@ --lockfile=libc.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)

        # Two levels
        client.save({"conanfile.py": GenConanfile().with_require("LibC/1.0")})
        client.run("create . LibD/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibD/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock")

        client.run("create . LibD/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        client.run("create . LibD/1.0@ --lockfile=libd.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)

    def test_partial_multiple_matches_lock(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        client.save({"conanfile.py": GenConanfile().with_require("LibB/1.0")
                                                   .with_require("LibA/[>=1.0]")})
        client.run("create . LibC/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibC/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibC --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libc.lock")

        client.run("create . LibC/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        client.run("create . LibC/1.0@ --lockfile=libc.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)

        # Two levels
        client.save({"conanfile.py": GenConanfile().with_require("LibC/1.0")})
        client.run("create . LibD/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibD/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock")

        client.run("create . LibD/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        client.run("create . LibD/1.0@ --lockfile=libd.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)

    def test_partial_lock_conflict(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})
        client.run("create . LibC/1.0@")

        client.save({"conanfile.py": GenConanfile().with_require("LibB/1.0")
                                                   .with_require("LibC/1.0")})
        client.run("create . LibD/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibD/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)
        self.assertNotIn("LibA/1.0.1", client.out)

        client.run("create . LibD/1.0@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        self.assertNotIn("LibA/1.0 from local", client.out)

        client.run("create . LibD/1.0@ --lockfile=libd.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)
        self.assertNotIn("LibA/1.0.1", client.out)

    def test_partial_lock_root_unused(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})

        client.run("create . LibC/1.0@ --lockfile=libb.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibC/1.0' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibC --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libc.lock")
        # Users can validate themselves if relevant package is in the lockfile or not
        libc_lock = client.load("libc.lock")
        self.assertNotIn("LibB/1.0", libc_lock)

    def test_remove_dep(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/0.1@")
        client.run("create . LibB/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require("LibA/0.1")
                                                   .with_require("LibB/0.1")})
        client.run("create . LibC/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require("LibC/0.1")})
        client.run("lock create conanfile.py --lockfile-out=conan.lock")
        lock = client.load("conan.lock")
        lock = json.loads(lock)["graph_lock"]["nodes"]
        self.assertEqual(4, len(lock))
        libc = lock["1"]
        liba = lock["2"]
        libb = lock["3"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(liba["ref"], "LibA/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(libb["ref"], "LibB/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(libc["ref"], "LibC/0.1#3cc68234fe3b976e1cb15c61afdace6d")
        else:
            self.assertEqual(liba["ref"], "LibA/0.1")
            self.assertEqual(libb["ref"], "LibB/0.1")
            self.assertEqual(libc["ref"], "LibC/0.1")
        self.assertEqual(libc["requires"], ["2", "3"])

        # Remove one dep (LibB) in LibC, will fail to create
        client.save({"conanfile.py": GenConanfile().with_require("LibA/0.1")})
        # If the graph is modified, a create should fail
        client.run("create . LibC/0.1@ --lockfile=conan.lock", assert_error=True)
        self.assertIn("Attempt to modify locked LibC/0.1", client.out)

        # It is possible to obtain a new lockfile
        client.run("export . LibC/0.1@")
        client.save({"conanfile.py": GenConanfile().with_require("LibC/0.1")})
        client.run("lock create conanfile.py --lockfile-out=new.lock")
        # And use the lockfile to build it
        client.run("install LibC/0.1@ --build=LibC --lockfile=new.lock")
        client.run("lock clean-modified new.lock")
        new_lock = client.load("new.lock")
        self.assertNotIn("modified", new_lock)
        new_lock_json = json.loads(new_lock)["graph_lock"]["nodes"]
        self.assertEqual(3, len(new_lock_json))
        libc = new_lock_json["1"]
        liba = new_lock_json["2"]
        if client.cache.config.revisions_enabled:
            self.assertEqual(liba["ref"], "LibA/0.1#f3367e0e7d170aa12abccb175fee5f97")
            self.assertEqual(libc["ref"], "LibC/0.1#ec5e114a9ad4f4269bc4a221b26eb47a")
        else:
            self.assertEqual(liba["ref"], "LibA/0.1")
            self.assertEqual(libc["ref"], "LibC/0.1")
        self.assertEqual(libc["requires"], ["2"])

    def test_add_dep(self):
        # https://github.com/conan-io/conan/issues/5807
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . zlib/1.0@")

        client.save({"conanfile.py": GenConanfile()})
        client.run("lock create conanfile.py --lockfile-out=conan.lock")
        client.save({"conanfile.py": GenConanfile().with_require("zlib/1.0")})
        client.run("install . --lockfile=conan.lock", assert_error=True)
        self.assertIn("ERROR: Require 'zlib' cannot be found in lockfile", client.out)

        # Correct way is generate a new lockfile
        client.run("lock create conanfile.py --lockfile-out=new.lock")
        self.assertIn("zlib/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self.assertIn("Generated lockfile", client.out)
        new = client.load("new.lock")
        lock_file_json = json.loads(new)
        self.assertEqual(2, len(lock_file_json["graph_lock"]["nodes"]))
        zlib = lock_file_json["graph_lock"]["nodes"]["1"]["ref"]
        if client.cache.config.revisions_enabled:
            self.assertEqual("zlib/1.0#f3367e0e7d170aa12abccb175fee5f97", zlib)
        else:
            self.assertEqual("zlib/1.0", zlib)

        # augment the existing one, works only because it is a consumer only, not package
        client.run("lock create conanfile.py --lockfile=conan.lock --lockfile-out=updated.lock")
        updated = client.load("updated.lock")
        self.assertEqual(updated, new)

    def test_augment_test_package_requires(self):
        # https://github.com/conan-io/conan/issues/6067
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("tool", "0.1")})
        client.run("create .")

        client.save({"conanfile.py": GenConanfile().with_name("dep").with_version("0.1"),
                     "test_package/conanfile.py": GenConanfile().with_test("pass"),
                     "consumer.txt": "[requires]\ndep/0.1\n",
                     "profile": "[build_requires]\ntool/0.1\n"})

        client.run("export .")
        client.run("lock create consumer.txt -pr=profile --build=missing --lockfile-out=conan.lock")
        lock1 = client.load("conan.lock")
        json_lock1 = json.loads(lock1)
        dep = json_lock1["graph_lock"]["nodes"]["1"]
        self.assertEqual(dep["build_requires"], ["2"])
        self.assertEqual(dep["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        if client.cache.config.revisions_enabled:
            self.assertEqual(dep["ref"], "dep/0.1#01b22a14739e1e2d4cd409c45cac6422")
            self.assertEqual(dep.get("prev"), None)
        else:
            self.assertEqual(dep["ref"], "dep/0.1")
            self.assertEqual(dep.get("prev"), None)

        client.run("create . --lockfile=conan.lock --lockfile-out=conan.lock "
                   "--build=missing")
        self.assertIn("dep/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        self.assertIn("tool/0.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        lock2 = client.load("conan.lock")
        json_lock2 = json.loads(lock2)
        dep = json_lock2["graph_lock"]["nodes"]["1"]
        self.assertEqual(dep["build_requires"], ["2"])
        self.assertEqual(dep["package_id"], "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        if client.cache.config.revisions_enabled:
            self.assertEqual(dep["ref"], "dep/0.1#01b22a14739e1e2d4cd409c45cac6422")
            self.assertEqual(dep["prev"], "08cd3e7664b886564720123959c05bdf")
        else:
            self.assertEqual(dep["ref"], "dep/0.1")
            self.assertEqual(dep["prev"], "0")

    def test_conditional_env_var(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . dep/1.0@")
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            import os
            class Pkg(ConanFile):
                def requirements(self):
                    if os.getenv("USE_DEP"):
                        self.requires("dep/1.0")
            """)
        client.save({"conanfile.py": conanfile})
        with environment_append({"USE_DEP": "1"}):
            client.run("lock create conanfile.py --name=pkg --version=1.0")
        lock = client.load("conan.lock")
        self.assertIn("dep/1.0", lock)

        client.run("create . pkg/1.0@ --lockfile=conan.lock", assert_error=True)
        self.assertIn("ERROR: 'pkg/1.0' locked requirement 'dep/1.0' not found", client.out)

    def test_partial_intermediate_package_lock(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("LibB/[>=1.0]")})
        client.run("create . LibC/1.0@")
        client.run("lock create --reference=LibC/1.0 --lockfile-out=libc.lock")

        # New version of LibA/1.0.1, that should never be used
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        # Go back to B, we want to develop but keep depending on LibA/1.0
        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})
        client.run("create . LibB/1.1@ --lockfile=libc.lock", assert_error=True)
        self.assertIn("Couldn't find 'LibB/1.1' in lockfile", client.out)

        client.run("lock create conanfile.py --name=LibB --version=1.1 --lockfile=libc.lock "
                   "--lockfile-out=libb.lock")
        self.assertIn("LibA/1.0 from local cache", client.out)
        self.assertNotIn("LibA/1.0.1", client.out)
        libb_lock = client.load("libb.lock")
        self.assertIn("LibA/1.0", libb_lock)
        self.assertNotIn("LibA/1.0.1", libb_lock)

        client.run("create . LibB/1.1@")
        self.assertIn("LibA/1.0.1 from local cache - Cache", client.out)
        client.run("create . LibB/1.1@ --lockfile=libb.lock")
        self.assertIn("LibA/1.0 from local cache - Cache", client.out)

    def test_relax_lockfile_to_build(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("LibA/[>=1.0]")})
        client.run("create . LibB/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require("LibB/[>=1.0]")})
        client.run("create . LibC/1.0@")
        client.run("lock create --reference=LibC/1.0 --lockfile-out=libc.lock")

        # New version of LibA/1.0.1, that should never be used
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . LibA/1.0.1@")

        client.run("lock create --reference=LibC/1.0 --build=LibC --lockfile=libc.lock "
                   "--lockfile-out=libc2.lock")
        libc2_json = json.loads(client.load("libc2.lock"))
        libc = libc2_json["graph_lock"]["nodes"]["1"]
        self.assertIn("LibC/1.0", libc["ref"])
        self.assertIsNone(libc.get("prev"))
        # Now it is possible to build it again
        client.run("install LibC/1.0@ --build=LibC --lockfile=libc2.lock --lockfile-out=libc3.lock")
        self.assertIn("LibC/1.0:3f278cfc7b3c4509db7f72c9bf2e472732c4f69f - Build", client.out)
        self.assertIn("LibC/1.0: Created package", client.out)
        libc3_json = json.loads(client.load("libc3.lock"))
        libc = libc3_json["graph_lock"]["nodes"]["1"]
        self.assertIn("LibC/1.0", libc["ref"])
        self.assertIsNotNone(libc.get("prev"))

        # Now unlock/build everything
        client.run("lock create --reference=LibC/1.0 --build --lockfile=libc3.lock "
                   "--lockfile-out=libc4.lock")
        client.run("lock build-order libc4.lock")
        self.assertIn("LibA/1.0@", client.out)
        self.assertIn("LibB/1.0@", client.out)
        self.assertIn("LibC/1.0@", client.out)


class PartialOptionsTest(unittest.TestCase):
    """
    When an option is locked in an existing lockfile, and we are using that lockfile to
    create a new one, and somehow the option is changed there are 2 options:
    - Allow the non-locked packages to change the value, according to the dependency resolution
      algorithm. That will produce a different package-id that will be detected and raise
      as incompatible to the locked one
    - Force the locked options, that will result in the same package-id. The package attempting
      to change that option, will not have it set, and can fail later (build time, link time)

    This test implements the 2nd approach, let the lockfile define the options values, not the
    package recipes
    """
    def setUp(self):
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_package_mode")
        client.save({"conanfile.py": GenConanfile().with_option("myoption", [True, False])})
        client.run("create . LibA/1.0@ -o LibA:myoption=True")
        self.assertIn("LibA/1.0:d2560ba1787c188a1d7fabeb5f8e012ac53301bb - Build", client.out)
        client.run("create . LibA/1.0@ -o LibA:myoption=False")
        self.assertIn("LibA/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build", client.out)
        self.client = client

    def test_partial_lock_option_command_line(self):
        # When 'LibA:myoption' is set in command line, the option value is saved in the
        # libb.lock and it is applied to all graph, overriding LibC.
        client = self.client
        client.save({"conanfile.py": GenConanfile().with_require("LibA/1.0")})
        client.run("create . LibB/1.0@ -o LibA:myoption=True")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock -o LibA:myoption=True")

        client.save({"conanfile.py": GenConanfile().with_require("LibA/1.0")
                                                   .with_default_option("LibA:myoption", False)})
        client.run("create . LibC/1.0@")
        self.assertIn("LibA/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)

        client.save({"conanfile.py": GenConanfile().with_require("LibB/1.0")
                                                   .with_require("LibC/1.0")})
        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock")
        self.assertIn("LibA/1.0:d2560ba1787c188a1d7fabeb5f8e012ac53301bb - Cache", client.out)
        self.assertIn("LibB/1.0:777a7717c781c687b6d0fecc05d3818d0a031f92 - Cache", client.out)
        self.assertIn("LibC/1.0:777a7717c781c687b6d0fecc05d3818d0a031f92 - Missing", client.out)

        # Order of LibC, LibB doesn't matter
        client.save({"conanfile.py": GenConanfile().with_require("LibC/1.0")
                                                   .with_require("LibB/1.0")})
        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock")
        self.assertIn("LibA/1.0:d2560ba1787c188a1d7fabeb5f8e012ac53301bb - Cache", client.out)
        self.assertIn("LibB/1.0:777a7717c781c687b6d0fecc05d3818d0a031f92 - Cache", client.out)
        self.assertIn("LibC/1.0:777a7717c781c687b6d0fecc05d3818d0a031f92 - Missing", client.out)

    def test_partial_lock_option_conanfile_default(self):
        # when 'LibA:myoption' is locked, it is used, even if other packages define it.
        client = self.client
        client.save({"conanfile.py": GenConanfile().with_require("LibA/1.0")
                                                   .with_default_option("LibA:myoption", True)})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        client.save({"conanfile.py": GenConanfile().with_require("LibA/1.0")
                                                   .with_default_option("LibA:myoption", False)})
        client.run("create . LibC/1.0@")
        self.assertIn("LibA/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self._check()

    def test_partial_lock_option_conanfile_configure(self):
        # when 'LibA:myoption' is locked, it is used, even if other packages define it.
        client = self.client
        client.save({"conanfile.py": GenConanfile().with_require("LibA/1.0")
                                                   .with_default_option("LibA:myoption", True)})
        client.run("create . LibB/1.0@")
        client.run("lock create --reference=LibB/1.0 --lockfile-out=libb.lock")

        libc = textwrap.dedent("""
            from conans import ConanFile
            class LibC(ConanFile):
                requires = "LibA/1.0"
                def configure(self):
                    self.options["LibA"].myoption = False
            """)
        client.save({"conanfile.py": libc})
        client.run("create . LibC/1.0@")
        self.assertIn("LibA/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", client.out)
        self._check()

    def _check(self):
        client = self.client

        client.save({"conanfile.py": GenConanfile().with_requires("LibB/1.0", "LibC/1.0")})
        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock", assert_error=True)
        expected = textwrap.dedent("""\
                       ERROR: LibA/1.0: Locked options do not match computed options
                       Locked options:
                       myoption=True
                       Computed options:
                       myoption=False""")
        self.assertIn(expected, client.out)

        # Order of LibC, LibB does matter, in this case it will not raise
        client.save({"conanfile.py": GenConanfile().with_requires("LibC/1.0", "LibB/1.0")})

        client.run("lock create conanfile.py --name=LibD --version=1.0 --lockfile=libb.lock "
                   "--lockfile-out=libd.lock")
        self.assertIn("LibC/1.0:777a7717c781c687b6d0fecc05d3818d0a031f92 - Missing", client.out)
