# coding=utf-8

import unittest

import pytest

from conans import Settings
from conans.client.conf import get_default_settings_yml
from conans.client.settings_preprocessor import preprocess
from conans.errors import ConanException


class SettingsCompilerIntelVisualPreprocessorTest(unittest.TestCase):

    def setUp(self):
        self.settings = Settings.loads(get_default_settings_yml())
        self.settings.compiler = "intel"
        self.settings.compiler.base = "Visual Studio"

    def test_release_build_type_runtime(self):
        self.settings.build_type = "Release"
        preprocess(self.settings)
        self.assertEqual(self.settings.compiler.base.runtime, "MD")

    def test_debug_build_type_runtime(self):
        self.settings.build_type = "Debug"
        preprocess(self.settings)
        self.assertEqual(self.settings.compiler.base.runtime, "MDd")

    def test_different_base_compiler(self):
        self.settings.compiler.base = "gcc"
        self.settings.build_type = "Debug"
        preprocess(self.settings)
        self.assertIsNone(self.settings.compiler.base.get_safe("runtime"))

    def test_custom_base_runtime_set(self):
        self.settings.build_type = "Debug"
        self.settings.compiler.base.runtime = "MT"
        preprocess(self.settings)
        self.assertEqual(self.settings.compiler.base.runtime, "MT")


class SettingsCompilerVisualPreprocessorTest(unittest.TestCase):

    def setUp(self):
        self.settings = Settings.loads(get_default_settings_yml())
        self.settings.compiler = "Visual Studio"

    def test_release_build_type_runtime(self):
        self.settings.build_type = "Release"
        preprocess(self.settings)
        self.assertEqual(self.settings.compiler.runtime, "MD")

    def test_debug_build_type_runtime(self):
        self.settings.build_type = "Debug"
        preprocess(self.settings)
        self.assertEqual(self.settings.compiler.runtime, "MDd")

    def test_different_base_compiler(self):
        self.settings.compiler = "gcc"
        self.settings.build_type = "Debug"
        preprocess(self.settings)
        self.assertIsNone(self.settings.compiler.get_safe("runtime"))

    def test_custom_base_runtime_set(self):
        self.settings.build_type = "Debug"
        self.settings.compiler.runtime = "MT"
        preprocess(self.settings)
        self.assertEqual(self.settings.compiler.runtime, "MT")


class TestSettingsCompilerMSVCPreprocessorTest:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.settings = Settings.loads(get_default_settings_yml())
        self.settings.compiler = "msvc"

    def test_release_build_type_runtime(self):
        self.settings.build_type = "Release"
        preprocess(self.settings)
        assert self.settings.compiler.runtime_type == "Release"

    def test_debug_build_type_runtime(self):
        self.settings.build_type = "Debug"
        preprocess(self.settings)
        assert self.settings.compiler.runtime_type == "Debug"

    def test_different_base_compiler(self):
        self.settings.compiler = "gcc"
        self.settings.build_type = "Debug"
        preprocess(self.settings)
        assert self.settings.compiler.get_safe("runtime") is None

    def test_custom_base_runtime_set(self):
        self.settings.build_type = "Debug"
        with pytest.raises(ConanException) as e:
            self.settings.compiler.runtime = "MT"
            preprocess(self.settings)
        assert "Invalid setting 'MT' is not a valid 'settings.compiler.runtime' value" \
               in str(e.value)
