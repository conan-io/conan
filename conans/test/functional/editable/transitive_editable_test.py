# coding=utf-8

import os
import unittest

from conans.test.utils.tools import TestClient
from conans.test.utils.conanfile import TestConanFile
from conans.util.files import mkdir


class TransitiveEditableTest(unittest.TestCase):

    def test_transitive_editables(self):
        # https://github.com/conan-io/conan/issues/4445
        client = TestClient()
        conanfileC = TestConanFile("LibC", "0.1")
        client.save({"conanfile.py": str(conanfileC)})
        client.run("editable add . LibC/0.1@user/testing")

        client2 = TestClient(client.cache_folder)
        conanfileB = TestConanFile("LibB", "0.1", requires=["LibC/0.1@user/testing"])

        client2.save({"conanfile.py": str(conanfileB)})
        client2.run("create . user/testing")

        conanfileA = TestConanFile("LibA", "0.1", requires=["LibB/0.1@user/testing",
                                                            "LibC/0.1@user/testing"])
        client2.save({"conanfile.py": str(conanfileA)})
        client2.run("install .")
        client2.current_folder = os.path.join(client2.current_folder, "build")
        mkdir(client2.current_folder)
        client2.run("install ..")
