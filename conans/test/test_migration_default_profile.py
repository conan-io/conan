import unittest
import os

from conans.client.migrations import migrate_to_default_profile
from conans.test.utils.test_files import temp_folder
from conans.util.files import save, load


class TestMigrationToDefaultProfile(unittest.TestCase):

    def test_something(self):
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

if __name__ == '__main__':
    unittest.main()
