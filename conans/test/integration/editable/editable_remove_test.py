# coding=utf-8

import unittest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class RemoveEditablePackageTest(unittest.TestCase):

    def setUp(self):
        self.t = TestClient()
        self.t.save(files={'conanfile.py': GenConanfile()})
        self.t.run('editable add . lib/version@user/name')
        self.t.run("editable list")
        assert "lib" in self.t.out

    def test_unlink(self):
        self.t.run('editable remove lib/version@user/name')
        self.assertIn("Removed editable mode for reference 'lib/version@user/name'", self.t.out)
        self.t.run("editable list")
        assert "lib" not in self.t.out

    def test_unlink_not_linked(self):
        self.t.run('editable remove otherlib/version@user/name')
        self.assertIn("Reference 'otherlib/version@user/name' was not installed as editable",
                      self.t.out)
        self.t.run("editable list")
        assert "lib" in self.t.out
