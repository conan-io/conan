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
        self.t.run('install --editable=. {}'.format(self.reference))
        self.assertTrue(self.t.client_cache.installed_as_editable(self.reference))

    def test_install_override(self):
        self.t.run('install {}'.format(self.reference), assert_error=True)
        self.assertIn("Removed '{}' as editable package".format(self.reference), self.t.out)

