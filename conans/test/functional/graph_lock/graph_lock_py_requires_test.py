import json
import textwrap
import unittest

from conans.model.graph_lock import LOCKFILE
from conans.test.utils.tools import TestClient, GenConanfile


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
    pkg_ref = "Pkg/0.1@user/channel#67fdc942d6157fc4db1971fd6d6c5c28"
    pkg_id = "1e1576940da80e70cd2d2ce2dddeb0571f91c6e3"
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
        client.save({"conanfile.py": self.consumer})
        client.run("install .")
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertIn("conanfile.py (Pkg/None): CONFIGURE VAR=42", client.out)
        self._check_lock("Pkg/None")

        client.run("build .")
        self.assertIn("conanfile.py (Pkg/None): CONFIGURE VAR=42", client.out)
        self.assertIn("conanfile.py (Pkg/None): BUILD VAR=42", client.out)

        # If we create a new Tool version
        client.save({"conanfile.py": conanfile.replace("42", "111")})
        client.run("export . Tool/0.2@user/channel")
        client.save({"conanfile.py": self.consumer})

    def _check_lock(self, ref_b, pkg_id_b=None):
        lock_file = self.client.load(LOCKFILE)
        self.assertIn("Tool/0.1@user/channel", lock_file)
        self.assertNotIn("Tool/0.2@user/channel", lock_file)
        lock_file_json = json.loads(lock_file)
        nodes = lock_file_json["graph_lock"]["nodes"]
        self.assertEqual(1, len(nodes))
        pkg = nodes["0"]
        self.assertEqual(pkg["ref"], ref_b)
        self.assertEqual(pkg["python_requires"],
                         ["Tool/0.1@user/channel#ac4036130c39cab7715b1402e8c211d3"])
        self.assertEqual(pkg.get("package_id"), pkg_id_b)

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
        self._check_lock("Pkg/None")
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
        self._check_lock(self.pkg_ref, self.pkg_id)

    def export_pkg_test(self):
        client = self.client
        client.run("export-pkg . Pkg/0.1@user/channel --install-folder=.  --lockfile")
        self.assertIn("Pkg/0.1@user/channel: CONFIGURE VAR=42", client.out)
        self._check_lock(self.pkg_ref, self.pkg_id)


class GraphLockPythonRequiresTest(GraphLockPyRequiresTest):
    pkg_ref = "Pkg/0.1@user/channel#332c2615c2ff9f78fc40682e733e5aa5"
    pkg_id = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
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
