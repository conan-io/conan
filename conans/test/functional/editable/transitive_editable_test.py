# coding=utf-8

import os
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
