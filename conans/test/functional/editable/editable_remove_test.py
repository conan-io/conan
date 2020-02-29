# coding=utf-8

import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


class RemoveEditablePackageTest(unittest.TestCase):
    conanfile = textwrap.dedent("""\
        from conans import ConanFile

        class APck(ConanFile):
            pass
        """)

    def setUp(self):
        self.ref = ConanFileReference.loads('lib/version@user/name')

        self.t = TestClient()
        self.t.save(files={'conanfile.py': self.conanfile,
                           "mylayout": "", })
        self.t.run('editable add . {} -l=mylayout'.format(self.ref))
        self.assertTrue(self.t.cache.installed_as_editable(self.ref))

    def test_unlink(self):
        self.t.run('editable remove {}'.format(self.ref))
        self.assertIn("Removed editable mode for reference '{}'".format(self.ref), self.t.out)
        self.assertFalse(self.t.cache.installed_as_editable(self.ref))

    def test_unlink_not_linked(self):
        reference = 'otherlib/version@user/name'
        self.t.run('search {}'.format(reference), assert_error=True)
        self.t.run('editable remove {}'.format(reference))
        self.assertIn("Reference '{}' was not installed as editable".format(reference), self.t.out)
