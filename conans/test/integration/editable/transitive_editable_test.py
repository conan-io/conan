# coding=utf-8

import os
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
