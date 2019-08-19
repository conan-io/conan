# coding=utf-8

import os
import textwrap
import unittest

from mock import patch

from conans.client.hook_manager import HookManager
from conans.model.ref import ConanFileReference
from conans.paths import CONAN_MANIFEST
from conans.test.utils.tools import TestClient


class PostPackageTestCase(unittest.TestCase):

    def test_manifest_creation(self):
        """ Test that 'post_package' hook is called before computing the manifest
        """

        ref = ConanFileReference.loads("name/version@user/channel")
        conanfile = textwrap.dedent("""\
            from conans import ConanFile

            class MyLib(ConanFile):
                pass
        """)

        t = TestClient()
        t.save({'conanfile.py': conanfile})

        def mocked_post_package(conanfile, **kwargs):
            # There shouldn't be a digest yet
            self.assertFalse(os.path.exists(os.path.join(conanfile.package_folder, CONAN_MANIFEST)))

        def mocked_load_hooks(hook_manager):
            hook_manager.hooks["post_package"] = [("_", mocked_post_package)]

        with patch.object(HookManager, "load_hooks", new=mocked_load_hooks):
            t.run("create . {}".format(ref))
        self.assertTrue(os.path.exists(os.path.join(conanfile.package_folder, CONAN_MANIFEST)))
