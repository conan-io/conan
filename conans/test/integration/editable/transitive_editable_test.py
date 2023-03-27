import os
import textwrap
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import mkdir


class TransitiveEditableTest(unittest.TestCase):

    @pytest.mark.xfail(reason="Editables not taken into account for cache2.0 yet."
                              "TODO: cache2.0 fix with editables")
    def test_transitive_editables(self):
        # https://github.com/conan-io/conan/issues/4445
        libc_ref = RecipeReference.loads("LibC/0.1@user/testing")
        libb_ref = RecipeReference.loads("LibB/0.1@user/testing")

        client = TestClient()
        conanfileC = GenConanfile()
        client.save({"conanfile.py": str(conanfileC)})
        client.run("editable add . LibC/0.1@user/testing")

        client2 = TestClient(client.cache_folder)
        conanfileB = GenConanfile().with_name("LibB").with_version("0.1").with_require(libc_ref)

        client2.save({"conanfile.py": str(conanfileB)})
        client2.run("create . --user=user --channel=testing")

        conanfileA = GenConanfile().with_name("LibA").with_version("0.1")\
                                   .with_require(libb_ref)\
                                   .with_require(libc_ref)
        client2.save({"conanfile.py": str(conanfileA)})
        client2.run("install .")
        client2.current_folder = os.path.join(client2.current_folder, "build")
        mkdir(client2.current_folder)
        client2.run("install ..")


def test_transitive_test_requires():
    c = TestClient()
    pkga = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeDeps, cmake_layout

        class Pkg(ConanFile):
            name = "pkga"
            version = "1.0"

            # Binary configuration
            settings = "os", "compiler", "build_type", "arch"

            def build_requirements(self):
                self.test_requires("gtest/1.0")

            def layout(self):
                cmake_layout(self)

            def generate(self):
                cd = CMakeDeps(self)
                cd.generate()
        """)
    pkgb = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class Pkg(ConanFile):
            name = "pkgb"
            version = "1.0"

            # Binary configuration
            settings = "os", "compiler", "build_type", "arch"

            def requirements(self):
                self.requires("pkga/1.0")

            def layout(self):
                cmake_layout(self)
            """)
    c.save({"gtest/conanfile.py": GenConanfile("gtest", "1.0"),
            "pkga/conanfile.py": pkga,
            "pkgb/conanfile.py": pkgb})
    c.run("create gtest")
    c.run("build pkga")
    c.run("editable add pkga")
    c.run("build pkgb")
