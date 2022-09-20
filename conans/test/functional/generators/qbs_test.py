import unittest

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class QbsGeneratorTest(unittest.TestCase):

    def test(self):
        client = TestClient()

        client.run("new dep/0.1 -b")
        client.run("create . user/testing")
        pkg = GenConanfile("pkg", "0.1").with_requires("dep/0.1@user/testing")
        client.save({"conanfile.py": pkg}, clean_first=True)
        client.run("create . user/testing")
        client.run("install pkg/0.1@user/testing -g=qbs")
        qbs = client.load("conanbuildinfo.qbs")
        self.assertIn('Depends { name: "dep" }', qbs)
