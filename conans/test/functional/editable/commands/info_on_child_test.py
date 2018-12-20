# coding=utf-8

import os
import textwrap
import unittest
from parameterized import parameterized
from conans.model.ref import ConanFileReference
from conans.paths.package_layouts.package_editable_layout import CONAN_PACKAGE_LAYOUT_FILE
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
        self.reference = ConanFileReference.loads('lib/version@user/name')
        self.child_ref = ConanFileReference.loads('child/version@user/name')

        self.t = TestClient(path_with_spaces=False)
        self.t.save(files={'conanfile.py': self.conanfile})
        self.t.run('create . {}'.format(self.ref_parent))

        lib_folder = os.path.join(self.t.current_folder, 'lib')
        self.t.save(files={'conanfile.py':
                               self.conanfile_base.format(body='requires = "{}"'.format(self.ref_parent)),
                           CONAN_PACKAGE_LAYOUT_FILE: self.conan_package_layout, },
                    path=lib_folder)
        self.t.run('link {} {}'.format(lib_folder, self.reference))
        self.assertTrue(self.t.client_cache.installed_as_editable(self.reference))

        # Create child
        self.t.save(files={'conanfile.py':
                          self.conanfile_base.format(body='requires = "{}"'.format(self.reference))})
        self.t.run('export . {}'.format(self.child_ref))

    @parameterized.expand([(True, ), (False, )])
    def test_no_args(self, use_local_path):
        args = "." if use_local_path else self.child_ref
        project_name = "PROJECT" if use_local_path else self.child_ref

        self.t.run('info {}'.format(args))
        self.assertIn("    Requires:\n"
                      "        lib/version@user/name\n"
                      "lib/version@user/name\n"
                      "    ID: e94ed0d45e4166d2f946107eaa208d550bf3691e\n"
                      "    BuildID: None\n"
                      "    Remote: None\n"
                      "    Recipe: Editable\n"
                      "    Binary: Editable\n"
                      "    Binary remote: None\n"
                      "    Required by:\n"
                      "        {}\n"
                      "    Requires:\n"
                      "        parent/version@user/name\n".format(project_name),
                      self.t.out)

    @parameterized.expand([(True,), (False,)])
    def test_only_none(self, use_local_path):
        args = "." if use_local_path else self.child_ref
        project_name = "PROJECT" if use_local_path else self.child_ref

        self.t.run('info {} --only None'.format(args))
        print(self.t.out)
        self.assertIn("{}\n"
                      "lib/version@user/name\n"
                      "parent/version@user/name".format(project_name), self.t.out)

    @parameterized.expand([(True,), (False,)])
    def test_paths(self, use_local_path):
        args = "." if use_local_path else self.child_ref
        self.t.run('info {} --paths'.format(args), assert_error=True)
        self.assertIn("ERROR: Operation not allowed on a package installed as editable", self.t.out)
        # TODO: Cannot show paths for a linked/editable package... what to do here?
