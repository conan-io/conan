# coding=utf-8

import os
import textwrap
import unittest

from parameterized import parameterized

from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class InfoCommandTest(unittest.TestCase):

    def setUp(self):
        self.ref = ConanFileReference.loads('lib/version@user/name')
        self.ref_child = ConanFileReference.loads('child/version@user/name')

        self.t = TestClient(path_with_spaces=False)
        self.t.save({'conanfile.py': GenConanfile()})
        self.t.run('create . parent/version@user/name')

        lib_folder = os.path.join(self.t.current_folder, 'lib')
        conan_package_layout = textwrap.dedent("""\
            [includedirs]
            src/include
            """)
        self.t.save({'lib/conanfile.py': GenConanfile().with_requires("parent/version@user/name"),
                     "lib/mylayout": conan_package_layout})
        self.t.run('editable add "{}" {}'.format(lib_folder, self.ref))
        self.assertTrue(self.t.cache.installed_as_editable(self.ref))

        # Create child
        self.t.save({'conanfile.py': GenConanfile().with_requires(self.ref)})
        self.t.run('export . {}'.format(self.ref_child))

    def tearDown(self):
        self.t.run('editable remove {}'.format(self.ref))
        self.assertFalse(self.t.cache.installed_as_editable(self.ref))

    @parameterized.expand([(True, ), (False, )])
    def test_no_args(self, use_local_path):
        project_name = "conanfile.py" if use_local_path else self.ref_child

        self.t.run('info {}'.format(project_name))
        revision = "    Revision: None\n"\
                   "    Package revision: None\n" \
                   if self.t.cache.config.revisions_enabled else ""
        self.assertIn("lib/version@user/name\n"
                      "    ID: e94ed0d45e4166d2f946107eaa208d550bf3691e\n"
                      "    BuildID: None\n"
                      "    Context: host\n"
                      "    Remote: None\n"
                      "    Provides: lib\n"
                      "    Recipe: Editable\n{}"
                      "    Binary: Editable\n"
                      "    Binary remote: None\n"
                      "    Required by:\n"
                      "        {}\n"
                      "    Requires:\n"
                      "        parent/version@user/name\n".format(revision, project_name),
                      self.t.out)

    @parameterized.expand([(True,), (False,)])
    def test_only_none(self, use_local_path):
        project_name = "conanfile.py" if use_local_path else self.ref_child

        self.t.run('info {} --only None'.format(project_name))
        # Compare, order is not guaranteed
        self.assertListEqual(sorted(str(self.t.out).splitlines()),
                             sorted(["lib/version@user/name",
                                     "parent/version@user/name",
                                     str(project_name)]))
