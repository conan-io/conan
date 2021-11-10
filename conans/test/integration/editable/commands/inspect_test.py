# coding=utf-8

import textwrap
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient


@pytest.mark.xfail(reason="Editables not taken into account for cache2.0 yet."
                          "TODO: cache2.0 fix with editables")
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
        self.ref_parent = RecipeReference.loads("parent/version@user/name")
        self.ref = RecipeReference.loads('lib/version@user/name')

        self.t = TestClient()
        self.t.save(files={'conanfile.py': self.conanfile})
        self.t.run('create . {}'.format(self.ref_parent))

        self.t.save(files={'conanfile.py':
                           self.conanfile_base.format(
                               body='requires = "{}"'.format(self.ref_parent)),
                           "mylayout": self.conan_package_layout, })
        self.t.run('editable add . {}'.format(self.ref))
        self.assertTrue(self.t.cache.installed_as_editable(self.ref))

    def tearDown(self):
        self.t.run('editable remove {}'.format(self.ref))
        self.assertFalse(self.t.cache.installed_as_editable(self.ref))

    def test_reference(self):
        self.t.run('inspect {}'.format(self.ref))
        self.assertIn("url: None", self.t.out)

        self.t.save(files={'conanfile.py': self.conanfile_base.format(body='url ="hh"')})
        self.t.run('inspect {}'.format(self.ref))
        self.assertIn('url: hh', self.t.out)
