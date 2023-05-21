import os
import textwrap
import unittest

from jinja2 import Template

from conans.client.cache.cache import ClientCache
from conans.client.conf import get_default_settings_yml
from conans.client.profile_loader import ProfileLoader
from conans.errors import ConanException
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class SettingsCppStdTests(unittest.TestCase):

    def setUp(self):
        self.tmp_folder = temp_folder()
        self.cache = ClientCache(self.tmp_folder)
        save(os.path.join(self.cache.plugins_path, "profile.py"), "")

    def _save_profile(self, compiler_cppstd=None, filename="default"):
        fullpath = os.path.join(self.cache.profiles_path, filename)

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
        fullpath = os.path.join(self.cache.profiles_path, "default")
        t = textwrap.dedent("""
            [settings]
            os=Macos
            arch=x86_64
            compiler=apple-clang
            compiler.libcxx=libc++
            compiler.version=10.0
            compiler.cppstd = 14
            """)
        save(self.cache.settings_path, get_default_settings_yml().replace("cppstd", "foobar"))
        save(fullpath, t)
        profile_loader = ProfileLoader(self.cache)
        with self.assertRaisesRegex(ConanException,
                                    "'settings.compiler.cppstd' doesn't exist for 'apple-clang'"):
            profile_loader.from_cli_args(["default"], None, None, None, None)

    def test_no_value(self):
        self._save_profile()
        profile_loader = ProfileLoader(self.cache)
        r = profile_loader.from_cli_args(["default"], None, None, None, None)
        self.assertNotIn("compiler.cppstd", r.settings)

    def test_value_none(self):
        self._save_profile(compiler_cppstd="None")
        profile_loader = ProfileLoader(self.cache)
        # It is incorrect to assign compiler.cppstd=None in the profile
        with self.assertRaisesRegex(ConanException, "Invalid setting"):
            r = profile_loader.from_cli_args(["default"], None, None, None, None)

    def test_value_valid(self):
        self._save_profile(compiler_cppstd="11")
        profile_loader = ProfileLoader(self.cache)
        r = profile_loader.from_cli_args(["default"], None, None, None, None)
        self.assertEqual(r.settings["compiler.cppstd"], "11")
        self.assertNotIn("cppstd", r.settings)

    def test_value_invalid(self):
        self._save_profile(compiler_cppstd="13")
        profile_loader = ProfileLoader(self.cache)
        with self.assertRaisesRegex(ConanException, "Invalid setting '13' is not a valid "
                                                    "'settings.compiler.cppstd' value"):
            r = profile_loader.from_cli_args(["default"], None, None, None, None)
