# coding=utf-8

import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.paths.package_layouts.package_editable_layout import CONAN_PACKAGE_LAYOUT_FILE
from conans.test.utils.tools import TestClient


class CommandsOnEditablePackageTest(unittest.TestCase):
    """ Check that commands info/inspect running over an editable package work"""

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
                          self.conanfile_base.format(body='requires = "{}"'.format(self.ref_parent)),
                      CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        self.t.run('export . {}'.format(self.reference))
        self.t.run('install --editable=. {}'.format(self.reference))
        self.assertTrue(self.t.client_cache.installed_as_editable(self.reference))

    def test_info_path(self):
        self.t.run('info .')
        self.assertIn("    Requires:\n        parent/version@user/name", self.t.out)

    def test_info_reference(self):
        self.t.run('info {}'.format(self.reference))
        self.assertIn("    Requires:\n        parent/version@user/name", self.t.out)

    def test_inspect_path(self):
        self.t.run('inspect .', assert_error=False)
        self.assertIn("url: None", self.t.out)  # To check anything

    def test_inspect_reference(self):
        self.t.run('inspect {}'.format(self.reference))
        self.assertIn("url: None", self.t.out)

        self.t.save(files={'conanfile.py': self.conanfile_base.format(body='url = "<url>"'), })
        self.t.run('inspect {}'.format(self.reference))
        self.assertIn("url: <url>", self.t.out)


class CommandsOnDependentPackageTest(unittest.TestCase):
    """ Check that commands info/inspect running over an editable package work"""

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
        self.reference = ConanFileReference.loads('lib/version@user/name')
        self.ref_child = ConanFileReference.loads("child/version@user/name")

        self.t = TestClient()
        self.t.save(files={'ref/conanfile.py': self.conanfile,
                           'ref/' + CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, })
        self.t.run('export ref/ {}'.format(self.reference))
        self.t.run('install --editable=ref/ {}'.format(self.reference))
        self.assertTrue(self.t.client_cache.installed_as_editable(self.reference))

        self.t.save(files={'conanfile.py':
                               self.conanfile_base.format(
                                   body='requires = "{}"'.format(self.reference)), })
        self.t.run('export . {}'.format(self.ref_child))

    def test_info_path(self):
        self.t.run('info .')
        self.assertIn("    Requires:\n        lib/version@user/name", self.t.out)

    def test_info_reference(self):
        self.t.run('info {}'.format(self.ref_child))
        self.assertIn("    Requires:\n        lib/version@user/name", self.t.out)

    def test_inspect_path(self):
        self.t.run('inspect .')  # Just to make sure it doesn't raise
        self.assertIn("url: None", self.t.out)

    def test_inspect_reference(self):
        self.t.run('inspect {}'.format(self.ref_child))  # Just to make sure it doesn't raise
        self.assertIn("url: None", self.t.out)

