# coding=utf-8

import os
import unittest

from mock import patch

from conans.client.hook_manager import HookManager
from conans.model.ref import ConanFileReference
from conans.paths import CONAN_MANIFEST
from conans.test.utils.tools import TurboTestClient


class PostPackageTestCase(unittest.TestCase):

    def test_create_command(self):
        """ Test that 'post_package' hook is called before computing the manifest
        """
        t = TurboTestClient()

        def post_package_hook(conanfile, **kwargs):
            # There shouldn't be a digest yet
            post_package_hook.manifest_path = os.path.join(conanfile.package_folder, CONAN_MANIFEST)
            self.assertFalse(os.path.exists(post_package_hook.manifest_path))

        def mocked_load_hooks(hook_manager):
            hook_manager.hooks["post_package"] = [("_", post_package_hook)]

        with patch.object(HookManager, "load_hooks", new=mocked_load_hooks):
            pref = t.create(ConanFileReference.loads("name/version@user/channel"))

        package_layout = t.cache.package_layout(pref.ref)
        self.assertEqual(post_package_hook.manifest_path,
                         os.path.join(package_layout.package(pref), CONAN_MANIFEST))
        self.assertTrue(os.path.exists(post_package_hook.manifest_path))

    def test_export_pkg_command(self):
        """ Test that 'post_package' hook is called before computing the manifest
        """
        t = TurboTestClient()

        def post_package_hook(conanfile, **kwargs):
            # There shouldn't be a digest yet
            post_package_hook.manifest_path = os.path.join(conanfile.package_folder, CONAN_MANIFEST)
            self.assertFalse(os.path.exists(post_package_hook.manifest_path))

        def mocked_load_hooks(hook_manager):
            hook_manager.hooks["post_package"] = [("_", post_package_hook)]

        with patch.object(HookManager, "load_hooks", new=mocked_load_hooks):
            pref = t.export_pkg(ref=ConanFileReference.loads("name/version@user/channel"),
                                args="--package-folder=.")

        package_layout = t.cache.package_layout(pref.ref)
        self.assertEqual(post_package_hook.manifest_path,
                         os.path.join(package_layout.package(pref), CONAN_MANIFEST))
        self.assertTrue(os.path.exists(post_package_hook.manifest_path))
