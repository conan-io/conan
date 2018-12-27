import os
import unittest

from six import StringIO

from conans.client.migrations import migrate_plugins_to_hooks, migrate_to_default_profile
from conans.client.output import ConanOutput
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import load, save


class TestMigrations(unittest.TestCase):

    def migration_to_default_profile_test(self):
        tmp = temp_folder()
        old_conf = """
[general]
the old general

[settings_defaults]
some settings

[other_section]

with other values

"""
        conf_path = os.path.join(tmp, "conan.conf")
        default_profile_path = os.path.join(tmp, "conan_default")
        save(conf_path, old_conf)

        migrate_to_default_profile(conf_path, default_profile_path)

        new_content = load(conf_path)
        self.assertEquals(new_content, """
[general]
the old general

[other_section]

with other values

""")

        default_profile = load(default_profile_path)
        self.assertEquals(default_profile, """[settings]
some settings""")

        old_conf = """
[general]
the old general

[settings_defaults]
some settings

"""
        conf_path = os.path.join(tmp, "conan.conf")
        default_profile_path = os.path.join(tmp, "conan_default")
        save(conf_path, old_conf)

        migrate_to_default_profile(conf_path, default_profile_path)
        default_profile = load(default_profile_path)
        self.assertEquals(default_profile, """[settings]
some settings""")

        new_content = load(conf_path)
        self.assertEquals(new_content, """
[general]
the old general

""")

    def migration_from_plugins_to_hooks_test(self):

        def _create_old_layout():
            old_user_home = temp_folder()
            old_conan_folder = os.path.join(old_user_home, ".conan")
            old_conf_path = os.path.join(old_conan_folder, "conan.conf")
            old_attribute_checker_plugin = os.path.join(old_conan_folder, "plugins",
                                                        "attribute_checker.py")
            save(old_conf_path, "\n[plugins]    # CONAN_PLUGINS\nattribute_checker")
            save(old_attribute_checker_plugin, "")
            # Do not adjust cpu_count, it is reusing a cache
            client_cache = TestClient(base_folder=old_user_home, cpu_count=False).client_cache
            assert old_conan_folder == client_cache.conan_folder
            return old_user_home, old_conan_folder, old_conf_path, old_attribute_checker_plugin,\
                   client_cache

        output = ConanOutput(StringIO())
        old_uh, old_cf, old_cp, old_acp, client_cache = _create_old_layout()
        migrate_plugins_to_hooks(client_cache, output=output)
        self.assertFalse(os.path.exists(old_acp))
        self.assertTrue(os.path.join(old_cf, "hooks"))
        conf_content = load(old_cp)
        self.assertNotIn("[plugins]", conf_content)
        self.assertIn("[hooks]", conf_content)

        # Test with a hook folder: Maybe there was already a hooks folder and a plugins folder
        old_uh, old_cf, old_cp, old_acp, client_cache = _create_old_layout()
        existent_hook = os.path.join(old_cf, "hooks", "hook.py")
        save(existent_hook, "")
        migrate_plugins_to_hooks(client_cache, output=output)
        self.assertTrue(os.path.exists(old_acp))
        self.assertTrue(os.path.join(old_cf, "hooks"))
        conf_content = load(old_cp)
        self.assertNotIn("[plugins]", conf_content)
        self.assertIn("[hooks]", conf_content)
