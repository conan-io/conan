import json
import os
import unittest

from six import StringIO

from conans import __version__
from conans.client.migrations import migrate_plugins_to_hooks, migrate_to_default_profile
from conans.client.output import ConanOutput
from conans.client.tools.version import Version
from conans.migrations import CONAN_VERSION
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import load, save


class TestMigrations(unittest.TestCase):

    def is_there_var_for_settings_previous_version_test(self):
        from conans import __version__ as current_version

        tmp = Version(current_version)
        if int(tmp.minor) == 0:
            return unittest.skip("2.0, this will make sense for 2.1")
        if int(tmp.patch) > 0:
            previous_version = "{}.{}.{}".format(tmp.major, tmp.minor, int(tmp.patch) - 1)
        else:
            previous_version = "{}.{}.0".format(tmp.major, int(tmp.minor) - 1)

        from conans.client import migrations_settings
        var_name = "settings_{}".format(previous_version.replace(".", "_"))
        self.assertTrue(any([i for i in dir(migrations_settings) if i == var_name]),
                        "Introduce the previous settings.yml file in the 'migrations_settings.yml")

    def test_migrate_revision_metadata(self):
        # https://github.com/conan-io/conan/issues/4898
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("Hello").with_version("0.1")})
        client.run("create . user/testing")
        ref = ConanFileReference.loads("Hello/0.1@user/testing")
        layout1 = client.cache.package_layout(ref)
        metadata = json.loads(load(layout1.package_metadata()))
        metadata["recipe"]["revision"] = None
        metadata["packages"]["WRONG"] = {"revision": ""}
        metadata["packages"]["5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"]["revision"] = None
        metadata["packages"]["5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"]["recipe_revision"] = None
        save(layout1.package_metadata(), json.dumps(metadata))

        client.run("create . user/stable")
        ref2 = ConanFileReference.loads("Hello/0.1@user/stable")
        layout2 = client.cache.package_layout(ref2)
        metadata = json.loads(load(layout2.package_metadata()))
        metadata["recipe"]["revision"] = "Other"
        save(layout2.package_metadata(), json.dumps(metadata))

        version_file = os.path.join(client.cache_folder, CONAN_VERSION)
        save(version_file, "1.14.1")
        client.run("search")  # This will fire a migration

        metadata_ref1 = client.cache.package_layout(ref).load_metadata()
        self.assertEqual(metadata_ref1.recipe.revision, "f9e0ab84b47b946f4c7c848d8f82d14e")
        pkg_metadata = metadata_ref1.packages["5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"]
        self.assertEqual(pkg_metadata.recipe_revision, "f9e0ab84b47b946f4c7c848d8f82d14e")
        self.assertEqual(pkg_metadata.revision, "fa1923ec4342a0d9dc33eff7250432e8")
        self.assertEqual(list(metadata_ref1.packages.keys()),
                         ["5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"])

        metadata_ref2 = client.cache.package_layout(ref2).load_metadata()
        self.assertEqual(metadata_ref2.recipe.revision, "Other")

    def test_migrate_config_install(self):
        client = TestClient()
        client.run('config set general.config_install="url, http:/fake.url, None, None"')
        version_file = os.path.join(client.cache_folder, CONAN_VERSION)
        save(version_file, "1.12.0")
        client.run("search")
        self.assertEqual(load(version_file), __version__)
        conf = load(client.cache.conan_conf_path)
        self.assertNotIn("http:/fake.url", conf)
        self.assertNotIn("config_install", conf)
        self.assertIn("http:/fake.url", load(client.cache.config_install_file))

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
        self.assertEqual(new_content, """
[general]
the old general

[other_section]

with other values

""")

        default_profile = load(default_profile_path)
        self.assertEqual(default_profile, """[settings]
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
        self.assertEqual(default_profile, """[settings]
some settings""")

        new_content = load(conf_path)
        self.assertEqual(new_content, """
[general]
the old general

""")

    def migration_from_plugins_to_hooks_test(self):

        def _create_old_layout():
            old_user_home = temp_folder()
            old_conan_folder = old_user_home
            old_conf_path = os.path.join(old_conan_folder, "conan.conf")
            old_attribute_checker_plugin = os.path.join(old_conan_folder, "plugins",
                                                        "attribute_checker.py")
            save(old_conf_path, "\n[general]\n[plugins]    # CONAN_PLUGINS\nattribute_checker")
            save(old_attribute_checker_plugin, "")
            # Do not adjust cpu_count, it is reusing a cache
            cache = TestClient(cache_folder=old_user_home, cpu_count=False).cache
            assert old_conan_folder == cache.cache_folder
            return old_user_home, old_conan_folder, old_conf_path, \
                old_attribute_checker_plugin, cache

        output = ConanOutput(StringIO())
        _, old_cf, old_cp, old_acp, cache = _create_old_layout()
        migrate_plugins_to_hooks(cache, output=output)
        self.assertFalse(os.path.exists(old_acp))
        self.assertTrue(os.path.join(old_cf, "hooks"))
        conf_content = load(old_cp)
        self.assertNotIn("[plugins]", conf_content)
        self.assertIn("[hooks]", conf_content)

        # Test with a hook folder: Maybe there was already a hooks folder and a plugins folder
        _, old_cf, old_cp, old_acp, cache = _create_old_layout()
        existent_hook = os.path.join(old_cf, "hooks", "hook.py")
        save(existent_hook, "")
        migrate_plugins_to_hooks(cache, output=output)
        self.assertTrue(os.path.exists(old_acp))
        self.assertTrue(os.path.join(old_cf, "hooks"))
        conf_content = load(old_cp)
        self.assertNotIn("[plugins]", conf_content)
        self.assertIn("[hooks]", conf_content)
