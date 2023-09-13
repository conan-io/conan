# coding=utf-8

import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import mkdir


class TransitiveEditableTest(unittest.TestCase):

    def test_transitive_editables(self):
        # https://github.com/conan-io/conan/issues/4445
        libc_ref = ConanFileReference.loads("LibC/0.1@user/testing")
        libb_ref = ConanFileReference.loads("LibB/0.1@user/testing")

        client = TestClient()
        conanfileC = GenConanfile()
        client.save({"conanfile.py": str(conanfileC)})
        client.run("editable add . LibC/0.1@user/testing")

        client2 = TestClient(client.cache_folder)
        conanfileB = GenConanfile().with_name("LibB").with_version("0.1").with_require(libc_ref)

        client2.save({"conanfile.py": str(conanfileB)})
        client2.run("create . user/testing")

        conanfileA = GenConanfile().with_name("LibA").with_version("0.1")\
                                   .with_require(libb_ref)\
                                   .with_require(libc_ref)
        client2.save({"conanfile.py": str(conanfileA)})
        client2.run("install .")
        client2.current_folder = os.path.join(client2.current_folder, "build")
        mkdir(client2.current_folder)
        client2.run("install ..")

    def test_transitive_editables_build(self):
        # https://github.com/conan-io/conan/issues/6064
        c = TestClient()
        c.run("config set general.default_package_id_mode=package_revision_mode")
        libb = textwrap.dedent("""\
            from conan import ConanFile
            class LibB(ConanFile):
                name = "libb"
                version = "0.1"
                build_policy = "missing"
                settings = "os", "compiler", "arch"

                def build_requirements(self):
                    self.build_requires("liba/[>=0.0]")

                def requirements(self):
                    self.requires("liba/[>=0.0]")
            """)
        c.save({"liba/conanfile.py": GenConanfile("liba", "0.1"),
                "libb/conanfile.py": libb,
                "app/conanfile.txt": "[requires]\nlibb/0.1"})
        c.run("editable add liba liba/0.1")
        c.run("editable add libb libb/0.1")
        c.run("install app --build=*")
        # It doesn't crash
        # Try also with 2 profiles
        c.run("install app -s:b os=Windows --build=*")
        # it doesn't crash
