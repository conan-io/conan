# coding=utf-8

import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


class LinkedPackageAsProject(unittest.TestCase):
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
        self.ref = ConanFileReference.loads('lib/version@user/name')

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


class InfoCommandOnLocalWorkspaceTest(LinkedPackageAsProject):
    """ Check that commands info/inspect running over an editable package work"""

    def test_no_args(self):
        self.t.run('info .')
        self.assertIn("conanfile.py\n"
                      "    ID: e94ed0d45e4166d2f946107eaa208d550bf3691e\n"
                      "    BuildID: None\n"
                      "    Requires:\n"
                      "        parent/version@user/name\n", self.t.out)

    def test_only_none(self):
        self.t.run('info . --only None')
        self.assertIn("parent/version@user/name\n"
                      "conanfile.py", self.t.out)

    def test_paths(self):
        self.t.run('info . --paths')
        self.assertIn("conanfile.py\n"
                      "    ID: e94ed0d45e4166d2f946107eaa208d550bf3691e\n"
                      "    BuildID: None\n"
                      "    Requires:\n"
                      "        parent/version@user/name\n", self.t.out)


class InfoCommandUsingReferenceTest(LinkedPackageAsProject):

    def test_no_args(self):
        self.t.run('info {}'.format(self.ref))
        rev = "    Revision: None\n" \
            if self.t.cache.config.revisions_enabled else ""  # Project revision is None
        expected = "lib/version@user/name\n" \
                   "    ID: e94ed0d45e4166d2f946107eaa208d550bf3691e\n" \
                   "    BuildID: None\n" \
                   "    Remote: None\n" \
                   "    Recipe: Editable\n{}" \
                   "    Binary: Editable\n" \
                   "    Binary remote: None\n" \
                   "    Requires:\n" \
                   "        parent/version@user/name\n".format(rev)
        self.assertIn(expected, self.t.out)

    def test_only_none(self):
        self.t.run('info {} --only None'.format(self.ref))
        self.assertListEqual(sorted(str(self.t.out).splitlines()),
                             sorted(["lib/version@user/name", "parent/version@user/name"]))

    def test_paths(self):
        self.t.run('info {} --paths'.format(self.ref), assert_error=True)
        self.assertIn("Operation not allowed on a package installed as editable", self.t.out)
        # TODO: Cannot show paths for a linked/editable package... what to do here?
