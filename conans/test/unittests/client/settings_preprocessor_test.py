# coding=utf-8

import unittest

from mock import mock

from conans import Settings
from conans.client.conf import default_settings_yml
from conans.client.settings_preprocessor import preprocess
from conans.test.utils.conanfile import MockSettings


class SettingsCompilerIntelVisualPreprocessorTest(unittest.TestCase):

    def setUp(self):
        self.settings = Settings.loads(default_settings_yml)
        self.settings.compiler = "intel"
        self.settings.compiler.base = "Visual Studio"

    def release_build_type_runtime_test(self):
        self.settings.build_type = "Release"
        preprocess(self.settings)
        self.assertEqual(self.settings.compiler.base.runtime, "MD")

    def debug_build_type_runtime_test(self):
        self.settings.build_type = "Debug"
        preprocess(self.settings)
        self.assertEqual(self.settings.compiler.base.runtime, "MDd")

    def different_base_compiler_test(self):
        self.settings.compiler.base = "gcc"
        self.settings.build_type = "Debug"
        preprocess(self.settings)
        self.assertIsNone(self.settings.compiler.base.get_safe("runtime"))

    def custom_base_runtime_set_test(self):
        self.settings.build_type = "Debug"
        self.settings.compiler.base.runtime = "MT"
        preprocess(self.settings)
        self.assertEqual(self.settings.compiler.base.runtime, "MT")

class SettingsCompilerVisualPreprocessorTest(unittest.TestCase):

    def setUp(self):
        self.settings = Settings.loads(default_settings_yml)
        self.settings.compiler = "Visual Studio"

    def release_build_type_runtime_test(self):
        self.settings.build_type = "Release"
        preprocess(self.settings)
        self.assertEqual(self.settings.compiler.runtime, "MD")

    def debug_build_type_runtime_test(self):
        self.settings.build_type = "Debug"
        preprocess(self.settings)
        self.assertEqual(self.settings.compiler.runtime, "MDd")

    def different_base_compiler_test(self):
        self.settings.compiler = "gcc"
        self.settings.build_type = "Debug"
        preprocess(self.settings)
        self.assertIsNone(self.settings.compiler.get_safe("runtime"))

    def custom_base_runtime_set_test(self):
        self.settings.build_type = "Debug"
        self.settings.compiler.runtime = "MT"
        preprocess(self.settings)
        self.assertEqual(self.settings.compiler.runtime, "MT")
