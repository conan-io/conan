import platform

import pytest

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class DefaultConfigTestCase(ConanV2ModeTestCase):

    @pytest.mark.xfail
    def test_package_id_mode(self):
        # TODO: Define package_id_mode for Conan v2
        t = self.get_client()
        self.fail("Define default package_id_mode for Conan v2")
        # self.assertEqual(t.cache.config.default_package_id_mode, "??")
        # t.run('config get general.default_package_id_mode')
        # self.assertEqual(str(t.out).strip(), "semver_direct_mode")

    @pytest.mark.skipif(platform.system() != "Linux", reason="OLD ABI is only detected for Linux/gcc")
    @pytest.mark.tool_gcc
    def test_default_libcxx(self):
        t = self.get_client()
        t.run('profile new --detect autodetected')
        self.assertNotIn("WARNING: GCC OLD ABI COMPATIBILITY", t.out)
        t.run('profile show autodetected')
        self.assertIn("compiler.libcxx=libstdc++11", t.out)
