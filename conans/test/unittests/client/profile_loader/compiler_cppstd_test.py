# coding=utf-8

import os
import textwrap
import unittest

import six
from jinja2 import Template

from conans.client.cache.cache import ClientCache
from conans.client.migrations_settings import settings_1_14_0
from conans.client.profile_loader import profile_from_args
from conans.errors import ConanException
from conans.test.utils.test_files import temp_folder
from conans.test.utils.mocks import TestBufferConanOutput
from conans.util.files import save


class SettingsCppStdTests(unittest.TestCase):

    def setUp(self):
        self.tmp_folder = temp_folder()
        self.cache = ClientCache(self.tmp_folder, TestBufferConanOutput())

    def _save_profile(self, cppstd=None, compiler_cppstd=None, filename="default"):
        fullpath = os.path.join(self.cache.profiles_path, filename)

        t = Template(textwrap.dedent("""
            [settings]
            os=Macos
            arch=x86_64
            compiler=apple-clang
            {% if compiler_cppstd %}compiler.cppstd={{ compiler_cppstd }}{% endif %}
            compiler.libcxx=libc++
            compiler.version=10.0
            {% if cppstd %}cppstd={{ cppstd }}{% endif %}
            """))

        save(fullpath, t.render(cppstd=cppstd, compiler_cppstd=compiler_cppstd))
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
        save(self.cache.settings_path, settings_1_14_0)
        save(fullpath, t)
        r = profile_from_args(["default", ], [], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        with six.assertRaisesRegex(self, ConanException,
                                   "'settings.compiler.cppstd' doesn't exist for 'apple-clang'"):
            r.process_settings(self.cache)

    def test_no_value(self):
        self._save_profile()

        r = profile_from_args(["default", ], [], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        r.process_settings(self.cache)
        self.assertNotIn("compiler.cppstd", r.settings)
        self.assertNotIn("cppstd", r.settings)

    def test_value_none(self):
        self._save_profile(compiler_cppstd="None")

        r = profile_from_args(["default", ], [], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        r.process_settings(self.cache)
        self.assertEqual(r.settings["compiler.cppstd"], "None")
        self.assertNotIn("cppstd", r.settings)

    def test_value_valid(self):
        self._save_profile(compiler_cppstd="11")

        r = profile_from_args(["default", ], [], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        r.process_settings(self.cache)
        self.assertEqual(r.settings["compiler.cppstd"], "11")
        self.assertNotIn("cppstd", r.settings)

    def test_value_invalid(self):
        self._save_profile(compiler_cppstd="13")

        r = profile_from_args(["default", ], [], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        with six.assertRaisesRegex(self, ConanException, "Invalid setting '13' is not a valid "
                                                         "'settings.compiler.cppstd' value"):
            r.process_settings(self.cache)
        self.assertNotIn("cppstd", r.settings)

    def test_value_duplicated_None(self):
        self._save_profile(compiler_cppstd="None", cppstd="None")

        r = profile_from_args(["default", ], [], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        r.process_settings(self.cache)
        self.assertEqual(r.settings["compiler.cppstd"], "None")
        self.assertEqual(r.settings["cppstd"], "None")

    def test_value_duplicated(self):
        self._save_profile(compiler_cppstd="11", cppstd="11")

        r = profile_from_args(["default", ], [], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        with six.assertRaisesRegex(self, ConanException, "Do not use settings 'compiler.cppstd'"
                                                         " together with 'cppstd'. Use only the"
                                                         " former one."):
            r.process_settings(self.cache)
        self.assertEqual(r.settings["compiler.cppstd"], "11")
        self.assertEqual(r.settings["cppstd"], "11")

    def test_value_different(self):
        self._save_profile(cppstd="14", compiler_cppstd="11")

        r = profile_from_args(["default", ], [], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        with six.assertRaisesRegex(self, ConanException, "Do not use settings 'compiler.cppstd'"
                                                         " together with 'cppstd'. Use only the"
                                                         " former one"):
            r.process_settings(self.cache)

    def test_value_from_cppstd(self):
        self._save_profile(cppstd="11")

        r = profile_from_args(["default", ], [], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        r.process_settings(self.cache)
        self.assertNotIn('compiler.cppstd', r.settings)
        self.assertEqual(r.settings["cppstd"], "11")
