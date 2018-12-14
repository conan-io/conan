# coding=utf-8

import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TestServer


class CreateEditablePackageTest(unittest.TestCase):

    conanfile = textwrap.dedent("""\
        from conans import ConanFile
        
        class APck(ConanFile):
            pass
        """)

    def test_install_existing(self):
        test_server = TestServer()
        servers = {"default": test_server}
        t = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        localpath_to_editable = os.path.join(t.current_folder, 'local', 'path')
        reference = ConanFileReference.loads('lib/version@user/name')

        t.save(files={os.path.join(localpath_to_editable, 'conanfile.py'): self.conanfile})
        t.run('create  "{}" {}'.format(localpath_to_editable, reference))  # TODO: Need to create first!!
        t.run('install --editable="{}" {}'.format(localpath_to_editable, reference))
        self.assertIn("Installed as editable!", t.out)

        self.assertTrue(t.client_cache.installed_as_editable(reference))
        layout = t.client_cache.package_layout(reference)
        self.assertTrue(layout.installed_as_editable())
        self.assertEqual(layout.conan(), localpath_to_editable)

    def test_install_not_existing(self):
        pass

    def test_install_with_deps(self):
        pass

    def test_editable_over_editable(self):
        pass

    def test_remove_editable(self):
        pass