import json
import os
import textwrap
import unittest

from conans.model.graph_lock import LOCKFILE
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import load


class GraphLockPyRequiresTransitiveTest(unittest.TestCase):
    def transitive_py_requires_test(self):
        # https://github.com/conan-io/conan/issues/5529
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . base/1.0@user/channel")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class PackageInfo(ConanFile):
                python_requires = "base/1.0@user/channel"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . helper/1.0@user/channel")

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class MyConanfileBase(ConanFile):
                python_requires = "helper/1.0@user/channel"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("install . pkg/0.1@user/channel")
        lockfile = client.load("conan.lock")
        self.assertIn("base/1.0@user/channel#f3367e0e7d170aa12abccb175fee5f97", lockfile)
        self.assertIn("helper/1.0@user/channel#539219485c7a9e8e19561db523512b39", lockfile)
        client.run("source .")
        self.assertIn("conanfile.py (pkg/0.1@user/channel): Configuring sources in", client.out)


class GraphLockPyRequiresTest(unittest.TestCase):
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
            from conans import ConanFile
            class Pkg(ConanFile):
                name = "Pkg"
                python_requires = "Tool/[>=0.1]@user/channel"
                def configure(self):
                    self.output.info("CONFIGURE VAR=%s" % self.python_requires["Tool"].module.var)
                def build(self):
                    self.output.info("BUILD VAR=%s" % self.python_requires["Tool"].module.var)
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
        lock_file = self.client.load(LOCKFILE)
        self.assertIn("Tool/0.1@user/channel", lock_file)
        self.assertNotIn("Tool/0.2@user/channel", lock_file)
        lock_file_json = json.loads(lock_file)
        self.assertEqual(1, len(lock_file_json["graph_lock"]["nodes"]))
        self.assertIn("%s:1e1576940da80e70cd2d2ce2dddeb0571f91c6e3" % ref_b, lock_file)
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
        self._check_lock("Pkg/0.1@user/channel#67fdc942d6157fc4db1971fd6d6c5c28")

    def export_pkg_test(self):
        client = self.client
        client.run("export-pkg . Pkg/0.1@user/channel --install-folder=.  --lockfile")
        self.assertIn("Pkg/0.1@user/channel: CONFIGURE VAR=42", client.out)
        self._check_lock("Pkg/0.1@user/channel#67fdc942d6157fc4db1971fd6d6c5c28")
