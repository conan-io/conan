# coding=utf-8

import os
import textwrap
import unittest

from parameterized import parameterized

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


class InfoCommandTest(unittest.TestCase):
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
        self.ref_child = ConanFileReference.loads('child/version@user/name')

        self.t = TestClient(path_with_spaces=False)
        self.t.save(files={'conanfile.py': self.conanfile})
        self.t.run('create . {}'.format(self.ref_parent))

        lib_folder = os.path.join(self.t.current_folder, 'lib')
        self.t.save(files={'conanfile.py':
                           self.conanfile_base.format(
                               body='requires = "{}"'.format(self.ref_parent)),
                           "mylayout": self.conan_package_layout, },
                    path=lib_folder)
        self.t.run('editable add "{}" {}'.format(lib_folder, self.ref))
        self.assertTrue(self.t.cache.installed_as_editable(self.ref))

        # Create child
        self.t.save(files={'conanfile.py':
                           self.conanfile_base.format(body='requires = "{}"'.format(self.ref))})
        self.t.run('export . {}'.format(self.ref_child))

    def tearDown(self):
        self.t.run('editable remove {}'.format(self.ref))
        self.assertFalse(self.t.cache.installed_as_editable(self.ref))

    @parameterized.expand([(True, ), (False, )])
    def test_no_args(self, use_local_path):
        args = "." if use_local_path else self.ref_child
        project_name = "conanfile.py" if use_local_path else self.ref_child

        self.t.run('info {}'.format(args))
        revision = "    Revision: None\n" if self.t.cache.config.revisions_enabled else ""
        self.assertIn("lib/version@user/name\n"
                      "    ID: e94ed0d45e4166d2f946107eaa208d550bf3691e\n"
                      "    BuildID: None\n"
                      "    Remote: None\n"
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
        args = "." if use_local_path else self.ref_child
        project_name = "conanfile.py" if use_local_path else self.ref_child

        self.t.run('info {} --only None'.format(args))
        # Compare, order is not guaranteed
        self.assertListEqual(sorted(str(self.t.out).splitlines()),
                             sorted(["lib/version@user/name",
                                     "parent/version@user/name",
                                     str(project_name)]))

    @parameterized.expand([(True,), (False,)])
    def test_paths(self, use_local_path):
        args = "." if use_local_path else self.ref_child
        self.t.run('info {} --paths'.format(args), assert_error=True)
        self.assertIn("ERROR: Operation not allowed on a package installed as editable", self.t.out)
        # TODO: Cannot show paths for a linked/editable package... what to do here?
