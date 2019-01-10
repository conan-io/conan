# coding=utf-8

import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.paths import CONAN_PACKAGE_LAYOUT_FILE
from conans.test.utils.tools import TestClient


class InspectCommandTest(unittest.TestCase):
    conanfile_base = textwrap.dedent("""\
        from conans import ConanFile

        class APck(ConanFile):
            {body}
        """)
    conanfile = conanfile_base.format(body="pass")

    conan_package_layout = textwrap.dedent("""\
        [includedirs]
        src/include
        """)

    def setUp(self):
        self.ref_parent = ConanFileReference.loads("parent/version@user/name")
        self.reference = ConanFileReference.loads('lib/version@user/name')

        self.t = TestClient()
        self.t.save(files={'conanfile.py': self.conanfile})
        self.t.run('create . {}'.format(self.ref_parent))

        self.t.save(files={'conanfile.py':
                           self.conanfile_base.format(
                               body='requires = "{}"'.format(self.ref_parent)),
                           CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        self.t.run('link . {}'.format(self.reference))
        self.assertTrue(self.t.client_cache.installed_as_editable(self.reference))

    def tearDown(self):
        self.t.run('link {} --remove'.format(self.reference))
        self.assertFalse(self.t.client_cache.installed_as_editable(self.reference))
        self.assertFalse(os.listdir(self.t.client_cache.conan(self.reference)))

    def test_reference(self):
        self.t.run('inspect {}'.format(self.reference))
        self.assertIn("url: None", self.t.out)

        self.t.save(files={'conanfile.py': self.conanfile_base.format(body='url ="hh"')})
        self.t.run('inspect {}'.format(self.reference))
        self.assertIn('url: hh', self.t.out)
