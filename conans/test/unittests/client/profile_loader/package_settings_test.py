# coding=utf-8

import os
import textwrap
import unittest

from conans.client.cache.cache import ClientCache
from conans.client.profile_loader import profile_from_args
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save


class SettingsCppStdTests(unittest.TestCase):

    def setUp(self):
        self.tmp_folder = temp_folder()
        self.cache = ClientCache(self.tmp_folder, TestBufferConanOutput())

    def test_compiler(self):
        profile = textwrap.dedent("""
            [settings]
            zlib:compiler=gcc
            compiler=Visual Studio
            """)
        save(os.path.join(self.cache.profiles_path, 'default'), profile)
        r = profile_from_args(["default", ], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        r.process_settings(self.cache)

        zlib_profile = r.package_settings("zlib")
        self.assertEqual(r.settings["compiler"], "Visual Studio")
        self.assertEqual(zlib_profile.settings["compiler"], "gcc")

    def test_fail_compiler(self):
        profile = textwrap.dedent("""
            [settings]
            zlib:compiler.libcxx=gcc
            compiler=Visual Studio
            """)
        save(os.path.join(self.cache.profiles_path, 'default'), profile)
        r = profile_from_args(["default", ], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        r.process_settings(self.cache)

        zlib_profile = r.package_settings("zlib")
        self.assertEqual(r.settings["compiler"], "Visual Studio")
        self.assertEqual(zlib_profile.settings["compiler"], "gcc")

    def test_fail_value(self):
        profile = textwrap.dedent("""
            [settings]
            zlib:compiler=tralala
            compiler=Visual Studio
            """)
        save(os.path.join(self.cache.profiles_path, 'default'), profile)
        r = profile_from_args(["default", ], [], [], [], cwd=self.tmp_folder, cache=self.cache)
        r.process_settings(self.cache)

        zlib_profile = r.package_settings("zlib")
        self.assertEqual(r.settings["compiler"], "Visual Studio")
        self.assertEqual(zlib_profile.settings["compiler"], "gcc")
