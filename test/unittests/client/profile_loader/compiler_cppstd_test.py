import os
import textwrap
import unittest

import yaml
from jinja2 import Template

from conan.internal.cache.cache import PkgCache
from conan.internal.cache.home_paths import HomePaths
from conans.client.conf import default_settings_yml
from conan.internal.api.profile.profile_loader import ProfileLoader
from conans.errors import ConanException
from conans.model.conf import ConfDefinition
from conans.model.settings import Settings
from conan.test.utils.test_files import temp_folder
from conans.util.files import save


class SettingsCppStdTests(unittest.TestCase):

    def setUp(self):
        self.cache_folder = temp_folder()
        self.cache = PkgCache(self.cache_folder, ConfDefinition())
        self.home_paths = HomePaths(self.cache_folder)
        save(self.home_paths.profile_plugin_path, "")

    def _save_profile(self, compiler_cppstd=None, filename="default"):
        fullpath = os.path.join(self.home_paths.profiles_path, filename)

        t = Template(textwrap.dedent("""
            [settings]
            os=Macos
            arch=x86_64
            compiler=apple-clang
            {% if compiler_cppstd %}compiler.cppstd={{ compiler_cppstd }}{% endif %}
            compiler.libcxx=libc++
            compiler.version=10.0
            """))

        save(fullpath, t.render(compiler_cppstd=compiler_cppstd))
        return filename

    def test_no_compiler_cppstd(self):
        # https://github.com/conan-io/conan/issues/5128
        fullpath = os.path.join(self.home_paths.profiles_path, "default")
        t = textwrap.dedent("""
            [settings]
            os=Macos
            arch=x86_64
            compiler=apple-clang
            compiler.libcxx=libc++
            compiler.version=10.0
            compiler.cppstd = 14
            """)
        save(fullpath, t)
        profile_loader = ProfileLoader(self.cache_folder)
        with self.assertRaisesRegex(ConanException,
                                    "'settings.compiler.cppstd' doesn't exist for 'apple-clang'"):
            profile = profile_loader.from_cli_args(["default"], None, None, None, None)
            settings = Settings(yaml.safe_load(default_settings_yml.replace("cppstd", "foobar")))
            profile.process_settings(settings)

    def test_no_value(self):
        self._save_profile()
        profile_loader = ProfileLoader(self.cache_folder)
        r = profile_loader.from_cli_args(["default"], None, None, None, None)
        self.assertNotIn("compiler.cppstd", r.settings)

    def test_value_none(self):
        self._save_profile(compiler_cppstd="None")
        profile_loader = ProfileLoader(self.cache_folder)
        # It is incorrect to assign compiler.cppstd=None in the profile
        with self.assertRaisesRegex(ConanException, "Invalid setting"):
            r = profile_loader.from_cli_args(["default"], None, None, None, None)
            settings = Settings(yaml.safe_load(default_settings_yml))
            r.process_settings(settings)

    def test_value_valid(self):
        self._save_profile(compiler_cppstd="11")
        profile_loader = ProfileLoader(self.cache_folder)
        r = profile_loader.from_cli_args(["default"], None, None, None, None)
        self.assertEqual(r.settings["compiler.cppstd"], "11")
        self.assertNotIn("cppstd", r.settings)

    def test_value_invalid(self):
        self._save_profile(compiler_cppstd="13")
        profile_loader = ProfileLoader(self.cache_folder)
        with self.assertRaisesRegex(ConanException, "Invalid setting '13' is not a valid "
                                                    "'settings.compiler.cppstd' value"):
            r = profile_loader.from_cli_args(["default"], None, None, None, None)
            settings = Settings(yaml.safe_load(default_settings_yml))
            r.process_settings(settings)
