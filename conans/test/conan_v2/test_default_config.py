import unittest

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class DefaultConfigTestCase(ConanV2ModeTestCase):
    def test_revisions_enabled(self):
        t = self.get_client()
        t.run('config get general.revisions_enabled')
        self.assertEqual(str(t.out).strip(), "1")

    @unittest.expectedFailure
    def test_package_id_mode(self):
        t = self.get_client()
        t.run('config get general.default_package_id_mode')
        self.fail("Define defualt package_id_mode for Conan v2")
        # self.assertEqual(str(t.out).strip(), "semver_direct_mode")
