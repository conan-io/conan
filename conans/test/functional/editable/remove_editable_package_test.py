# coding=utf-8

import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.paths.package_layouts.package_editable_layout import CONAN_PACKAGE_LAYOUT_FILE
from conans.test.utils.tools import TestClient


class RemoveEditablePackageTest(unittest.TestCase):
    conanfile = textwrap.dedent("""\
        from conans import ConanFile

        class APck(ConanFile):
            pass
        """)

    def setUp(self):
        self.reference = ConanFileReference.loads('lib/version@user/name')

        self.t = TestClient()
        self.t.save(files={'conanfile.py': self.conanfile,
                           CONAN_PACKAGE_LAYOUT_FILE: "", })
        self.t.run('export  . {}'.format(self.reference))  # No need to export, will create it on the fly
        self.t.run('link . {}'.format(self.reference))
        self.assertTrue(self.t.client_cache.installed_as_editable(self.reference))

    def test_unlink(self):
        self.t.run('link {} --remove'.format(self.reference))
        self.assertIn("Removed linkage for reference '{}'".format(self.reference), self.t.out)

