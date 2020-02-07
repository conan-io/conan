import platform
import unittest

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class DefaultConfigTestCase(ConanV2ModeTestCase):
    def test_revisions_enabled(self):
        import os
        print("CONAN_V2_MODE_ENVVAR: {}".format(os.environ.get('CONAN_V2_MODE', '-----')))
        print("TESTING_REVISIONS_ENABLED: {}".format(os.environ.get('TESTING_REVISIONS_ENABLED', '-----')))
        t = self.get_client()
        c = t.load(os.path.join(t.cache_folder, 'conan.conf'))
        print(c)
        t.run('config get general.revisions_enabled')
        self.assertEqual(str(t.out).strip(), "1")

    @unittest.expectedFailure
    def test_package_id_mode(self):
        t = self.get_client()
        t.run('config get general.default_package_id_mode')
        self.fail("Define default package_id_mode for Conan v2")
        # self.assertEqual(str(t.out).strip(), "semver_direct_mode")

    @unittest.skipUnless(platform.system() == "Linux", "OLD ABI is only detected for Linux/gcc")
    def test_default_libcxx(self):
        t = self.get_client()
        t.run('profile new --detect autodetected')
        self.assertNotIn("WARNING: GCC OLD ABI COMPATIBILITY", t.out)
        t.run('profile show autodetected')
        self.assertIn("compiler.libcxx=libstdc++11", t.out)
