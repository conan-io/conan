import os
import textwrap
import unittest
import warnings

import six

from conans.client.profile_loader import read_profile
from conans.errors import ConanV2Exception
from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class ProfileLoaderTestCase(ConanV2ModeTestCase):

    def test_profile_scopes(self):
        content = textwrap.dedent("""
            [settings]
            os=Linux
            [scopes]
        """)
        folder = temp_folder()
        save(os.path.join(folder, 'myprofile'), content)
        with six.assertRaisesRegex(self, ConanV2Exception, "Conan v2 incompatible: Field 'scopes' in profile is deprecated"):
            read_profile('myprofile', cwd=folder, default_folder=folder)


class ProfileLoaderV1TestCase(unittest.TestCase):

    def test_profile_scopes(self):
        content = textwrap.dedent("""
            [settings]
            os=Linux
            [scopes]
        """)
        folder = temp_folder()
        save(os.path.join(folder, 'myprofile'), content)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            read_profile('myprofile', cwd=folder, default_folder=folder)

            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))