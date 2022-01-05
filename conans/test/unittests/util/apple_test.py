#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import platform
import unittest

import pytest

from conan.tools.apple.apple import apple_sdk_name, to_apple_arch, XCRun, apple_min_version_flag, \
    is_apple_os
from conans.test.utils.mocks import MockConanfile


class FakeSettings(object):
    def __init__(self, _os, arch, os_sdk=None, os_version=None, subsystem=None):
        self._os = _os
        self._arch = arch
        self._os_sdk = os_sdk
        self._os_version = os_version
        self._os_subystem = subsystem

    def get_safe(self, name):
        if name == 'os':
            return self._os
        elif name == 'arch':
            return self._arch
        elif name == 'os.sdk':
            return self._os_sdk
        elif name == "os.version":
            return self._os_version
        elif name == "os.subsystem":
            return self._os_subystem


class TestApple:
    @pytest.mark.parametrize("os_, version, sdk, subsystem, flag",
                             [("Macos", "10.1", None, None, '-mmacosx-version-min=10.1'),
                              ("Macos", "10.1", "macosx", None, '-mmacosx-version-min=10.1'),
                              ("iOS", "10.1", None, None, '-mios-version-min=10.1'),
                              ("iOS", "10.1", "iphoneos", None, '-mios-version-min=10.1'),
                              ("iOS", "10.1", "iphonesimulator", None,
                               '-mios-simulator-version-min=10.1'),
                              ("watchOS", "10.1", None, None, '-mwatchos-version-min=10.1'),
                              ("watchOS", "10.1", "watchos", None, '-mwatchos-version-min=10.1'),
                              ("watchOS", "10.1", "watchsimulator", None,
                               '-mwatchos-simulator-version-min=10.1'),
                              ("tvOS", "10.1", None, None, '-mtvos-version-min=10.1'),
                              ("tvOS", "10.1", "appletvos", None, '-mtvos-version-min=10.1'),
                              ("tvOS", "10.1", "appletvsimulator", None,
                               '-mtvos-simulator-version-min=10.1'),
                              ("Macos", "10.1", None, "catalyst", '-mios-version-min=10.1'),
                              ("Macos", "10.1", "macosx", "catalyst", '-mios-version-min=10.1'),
                              ("Solaris", "10.1", None, None, ''),
                              ])
    def test_deployment_target_flag_name(self, os_, version, sdk, subsystem, flag):
        assert apple_min_version_flag(version, sdk, subsystem) == flag


class AppleTest(unittest.TestCase):
    def test_is_apple_os(self):
        self.assertTrue(is_apple_os('iOS'))
        self.assertTrue(is_apple_os('tvOS'))
        self.assertTrue(is_apple_os('watchOS'))
        self.assertTrue(is_apple_os('Macos'))
        self.assertFalse(is_apple_os('Windows'))
        self.assertFalse(is_apple_os('Linux'))
        self.assertFalse(is_apple_os('Android'))

    def test_to_apple_arch(self):
        self.assertEqual(to_apple_arch('x86'), 'i386')
        self.assertEqual(to_apple_arch('x86_64'), 'x86_64')
        self.assertEqual(to_apple_arch('armv7'), 'armv7')
        self.assertEqual(to_apple_arch('armv7s'), 'armv7s')
        self.assertEqual(to_apple_arch('armv7k'), 'armv7k')
        self.assertEqual(to_apple_arch('armv8'), 'arm64')
        self.assertEqual(to_apple_arch('armv8.3'), 'arm64e')
        self.assertEqual(to_apple_arch('armv8_32'), 'arm64_32')
        self.assertIsNone(to_apple_arch('mips'))

    def test_apple_sdk_name(self):
        self.assertEqual(apple_sdk_name(FakeSettings('Macos', 'x86')), 'macosx')
        self.assertEqual(apple_sdk_name(FakeSettings('Macos', 'x86_64')), 'macosx')
        self.assertEqual(apple_sdk_name(FakeSettings('iOS', 'x86_64')), 'iphonesimulator')
        self.assertEqual(apple_sdk_name(FakeSettings('iOS', 'armv7')), 'iphoneos')
        self.assertEqual(apple_sdk_name(FakeSettings('watchOS', 'x86_64')), 'watchsimulator')
        self.assertEqual(apple_sdk_name(FakeSettings('watchOS', 'armv7k')), 'watchos')
        self.assertEqual(apple_sdk_name(FakeSettings('tvOS', 'x86')), 'appletvsimulator')
        self.assertEqual(apple_sdk_name(FakeSettings('tvOS', 'armv8')), 'appletvos')
        self.assertIsNone(apple_sdk_name(FakeSettings('Windows', 'x86')))

        self.assertEqual(apple_sdk_name(FakeSettings('iOS', 'armv8')), 'iphoneos')
        self.assertEqual(apple_sdk_name(FakeSettings('iOS', 'armv8', 'iphoneos')),
                         'iphoneos')
        self.assertEqual(apple_sdk_name(FakeSettings('iOS', 'armv8', 'iphonesimulator')),
                         'iphonesimulator')

    def test_apple_sdk_name_custom_settings(self):
        self.assertEqual(apple_sdk_name(FakeSettings('Macos', 'ios_fat')), 'macosx')
        self.assertEqual(apple_sdk_name(FakeSettings('iOS', 'ios_fat')), 'iphoneos')
        self.assertEqual(apple_sdk_name(FakeSettings('watchOS', 'ios_fat')), 'watchos')
        self.assertEqual(apple_sdk_name(FakeSettings('tvOS', 'ios_fat')), 'appletvos')
        self.assertIsNone(apple_sdk_name(FakeSettings('ConanOS', 'ios_fat')))

    @pytest.mark.skipif(platform.system() != "Darwin", reason="Requires OSX")
    def test_xcrun(self):

        def _common_asserts(xcrun_):
            self.assertTrue(xcrun_.cc.endswith('clang'))
            self.assertTrue(xcrun_.cxx.endswith('clang++'))
            self.assertTrue(xcrun_.ar.endswith('ar'))
            self.assertTrue(xcrun_.ranlib.endswith('ranlib'))
            self.assertTrue(xcrun_.strip.endswith('strip'))
            self.assertTrue(xcrun_.find('lipo').endswith('lipo'))
            self.assertTrue(os.path.isdir(xcrun_.sdk_path))

        settings = FakeSettings('Macos', 'x86')
        xcrun = XCRun(settings)
        _common_asserts(xcrun)

        settings = FakeSettings('iOS', 'x86')
        xcrun = XCRun(settings, sdk='macosx')
        _common_asserts(xcrun)
        # Simulator
        self.assertNotIn("iPhoneOS", xcrun.sdk_path)

        settings = FakeSettings('iOS', 'armv7')
        xcrun = XCRun(settings)
        _common_asserts(xcrun)
        self.assertIn("iPhoneOS", xcrun.sdk_path)

        settings = FakeSettings('watchOS', 'armv7')
        xcrun = XCRun(settings)
        _common_asserts(xcrun)
        self.assertIn("WatchOS", xcrun.sdk_path)

        # Default one
        settings = FakeSettings(None, None)
        xcrun = XCRun(settings)
        _common_asserts(xcrun)
