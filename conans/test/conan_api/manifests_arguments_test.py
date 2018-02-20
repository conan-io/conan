from conans.client.conan_api import _parse_manifests_arguments, ConanException, default_manifest_folder
import unittest
from nose_parameterized.parameterized import parameterized
import os


class ArgumentsTest(unittest.TestCase):
    @parameterized.expand([
        (dict(verify=default_manifest_folder,
              manifests=default_manifest_folder,
              manifests_interactive=default_manifest_folder),),
        (dict(verify=None,
              manifests=default_manifest_folder,
              manifests_interactive=default_manifest_folder),),
        (dict(verify=default_manifest_folder,
              manifests=None,
              manifests_interactive=default_manifest_folder),),
        (dict(verify=default_manifest_folder,
              manifests=default_manifest_folder,
              manifests_interactive=None),),
        (dict(verify=default_manifest_folder,
              manifests=None,
              manifests_interactive=None),),
    ])
    def test_manifest_arguments_conflicting(self, arguments):
        with self.assertRaises(ConanException):
            _parse_manifests_arguments(cwd=None, **arguments)

    def test_manifests_arguments_verify(self):
        cwd = os.getcwd()
        manifests = _parse_manifests_arguments(verify=default_manifest_folder,
                                               manifests=None,
                                               manifests_interactive=None,
                                               cwd=cwd)
        manifest_folder, manifest_interactive, manifest_verify = manifests

        self.assertIn(cwd, manifest_folder)
        self.assertFalse(manifest_interactive)
        self.assertTrue(manifest_verify)

    def test_manifests_arguments_manifests_interactive(self):
        cwd = os.getcwd()
        manifests = _parse_manifests_arguments(verify=None,
                                               manifests=None,
                                               manifests_interactive=default_manifest_folder,
                                               cwd=cwd)
        manifest_folder, manifest_interactive, manifest_verify = manifests

        self.assertIn(cwd, manifest_folder)
        self.assertTrue(manifest_interactive)
        self.assertFalse(manifest_verify)

    def test_manifests_arguments_manifests(self):
        cwd = os.getcwd()
        manifests = _parse_manifests_arguments(verify=None,
                                               manifests=default_manifest_folder,
                                               manifests_interactive=None,
                                               cwd=cwd)
        manifest_folder, manifest_interactive, manifest_verify = manifests

        self.assertIn(cwd, manifest_folder)
        self.assertFalse(manifest_interactive)
        self.assertFalse(manifest_verify)

    def test_manifests_arguments_no_manifests(self):
        cwd = os.getcwd()
        manifests = _parse_manifests_arguments(verify=None, manifests=None, manifests_interactive=None, cwd=cwd)
        manifest_folder, manifest_interactive, manifest_verify = manifests

        self.assertIsNone(manifest_folder)
        self.assertFalse(manifest_interactive)
        self.assertFalse(manifest_verify)
