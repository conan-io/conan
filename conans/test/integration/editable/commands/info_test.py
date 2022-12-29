# coding=utf-8
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class LinkedPackageAsProject(unittest.TestCase):

    def setUp(self):
        self.ref = ConanFileReference.loads('lib/version@user/name')

        self.t = TestClient()
        self.t.save({'conanfile.py': GenConanfile()})
        self.t.run('create . parent/version@user/name')
        conan_package_layout = textwrap.dedent("""\
            [includedirs]
            src/include
            """)
        self.t.save({'conanfile.py': GenConanfile().with_require("parent/version@user/name"),
                     "mylayout": conan_package_layout})
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
                      "    Context: host\n"
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
                      "    Context: host\n"
                      "    Requires:\n"
                      "        parent/version@user/name\n", self.t.out)


class InfoCommandUsingReferenceTest(LinkedPackageAsProject):

    def test_no_args(self):
        self.t.run('info {}'.format(self.ref))
        rev = "    Revision: None\n"\
              "    Package revision: None\n" \
              if self.t.cache.config.revisions_enabled else ""  # Project revision is None
        expected = "lib/version@user/name\n" \
                   "    ID: e94ed0d45e4166d2f946107eaa208d550bf3691e\n" \
                   "    BuildID: None\n" \
                   "    Context: host\n" \
                   "    Remote: None\n" \
                   "    Provides: lib\n" \
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


def test_info_paths():
    # https://github.com/conan-io/conan/issues/7054
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            def layout(self):
                self.folders.source = "."
                self.folders.build = "."
        """)
    c.save({"pkg/conanfile.py": conanfile,
            "consumer/conanfile.py": GenConanfile().with_require("pkg/0.1")})
    c.run("editable add pkg pkg/0.1@")
    c.run("info consumer --paths")
    # TODO: Conan 2.0: see if it is possible to get the full actual values
    assert "export_folder:" in c.out  # Important bit is it doesn't raise an error
