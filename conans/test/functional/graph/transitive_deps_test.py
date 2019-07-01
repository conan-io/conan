# coding=utf-8

import os
import unittest

from parameterized import parameterized

from conans.model.ref import PackageReference
from conans.test.utils.conanfile import TestConanFile
from conans.test.utils.tools import TestClient
from conans.util.files import load


class TransitiveDepsTest(unittest.TestCase):

    def setUp(self):
        # Create dependency graph: C -> B -> A
        self.t = TestClient()

        self.t.save({"A/conanfile.py": str(TestConanFile("AAAA", "1.0"))})
        self.t.run("export A user/channel")

        self.t.save({"B/conanfile.py": str(TestConanFile("BBBB", "1.0",
                                                         requires=["AAAA/1.0@user/channel"]))})
        self.t.run("export B user/channel")
        self.t.save({"C/conanfile.py":
                     str(TestConanFile("CCCC", "1.0", requires=["BBBB/1.0@user/channel"])) +
                    "    generators='cmake'"})
        self.t.run("export C user/channel")

    @parameterized.expand([(True, ), (False, )])
    def test_consume(self, inverse_order):
        deps = sorted(["AAAA/1.0@user/channel", "CCCC/1.0@user/channel"], reverse=inverse_order)

        # Create D -> A,C
        self.t.save({"D/conanfile.py": str(TestConanFile("DDDD", "1.0",
                                                         requires=deps))})
        self.t.run("create ./D user/channel --build=missing")

        # C is being built
        pref_c = PackageReference.loads(
            "CCCC/1.0@user/channel:aef99e6ca67e3d2da47927c4ec1ec7129129943f")
        self.assertIn("{} - Build".format(pref_c), self.t.out)
        build_folder = self.t.cache.package_layout(pref_c.ref).build(pref_c)

        # It contains information about AAAA
        conanbuildinfo = load(os.path.join(build_folder, "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_AAAA_ROOT ", conanbuildinfo)
