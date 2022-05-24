#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import platform
import unittest

import pytest

from conans.client import tools


class FakeSettings(object):
    def __init__(self, _os, _arch, _os_sdk=None):
        self._os = _os
        self._arch = _arch
        self._os_sdk = _os_sdk

    def get_safe(self, name):
        if name == 'os':
            return self._os
        elif name == 'arch':
            return self._arch
        elif name == 'os.sdk':
            return self._os_sdk


class AppleTest(unittest.TestCase):
    def test_is_apple_os(self):
        self.assertTrue(tools.is_apple_os('iOS'))
        self.assertTrue(tools.is_apple_os('tvOS'))
        self.assertTrue(tools.is_apple_os('watchOS'))
        self.assertTrue(tools.is_apple_os('Macos'))
        self.assertFalse(tools.is_apple_os('Windows'))
        self.assertFalse(tools.is_apple_os('Linux'))
        self.assertFalse(tools.is_apple_os('Android'))

    def test_to_apple_arch(self):
        self.assertEqual(tools.to_apple_arch('x86'), 'i386')
        self.assertEqual(tools.to_apple_arch('x86_64'), 'x86_64')
        self.assertEqual(tools.to_apple_arch('armv7'), 'armv7')
        self.assertEqual(tools.to_apple_arch('armv7s'), 'armv7s')
        self.assertEqual(tools.to_apple_arch('armv7k'), 'armv7k')
        self.assertEqual(tools.to_apple_arch('armv8'), 'arm64')
        self.assertEqual(tools.to_apple_arch('armv8.3'), 'arm64e')
        self.assertEqual(tools.to_apple_arch('armv8_32'), 'arm64_32')
        self.assertIsNone(tools.to_apple_arch('mips'))

    def test_apple_sdk_name(self):
        self.assertEqual(tools.apple_sdk_name(FakeSettings('Macos', 'x86')), 'macosx')
        self.assertEqual(tools.apple_sdk_name(FakeSettings('Macos', 'x86_64')), 'macosx')
        self.assertEqual(tools.apple_sdk_name(FakeSettings('iOS', 'x86_64')), 'iphonesimulator')
        self.assertEqual(tools.apple_sdk_name(FakeSettings('iOS', 'armv7')), 'iphoneos')
        self.assertEqual(tools.apple_sdk_name(FakeSettings('watchOS', 'x86_64')), 'watchsimulator')
        self.assertEqual(tools.apple_sdk_name(FakeSettings('watchOS', 'armv7k')), 'watchos')
        self.assertEqual(tools.apple_sdk_name(FakeSettings('tvOS', 'x86')), 'appletvsimulator')
        self.assertEqual(tools.apple_sdk_name(FakeSettings('tvOS', 'armv8')), 'appletvos')
        self.assertIsNone(tools.apple_sdk_name(FakeSettings('Windows', 'x86')))

        self.assertEqual(tools.apple_sdk_name(FakeSettings('iOS', 'armv8')), 'iphoneos')
        self.assertEqual(tools.apple_sdk_name(FakeSettings('iOS', 'armv8', 'iphoneos')),
                         'iphoneos')
        self.assertEqual(tools.apple_sdk_name(FakeSettings('iOS', 'armv8', 'iphonesimulator')),
                         'iphonesimulator')

    def test_apple_sdk_name_build_folder_vars(self):
        self.assertEqual(tools.apple_sdk_name(FakeSettings('Macos', 'ios_fat')), 'macosx')
        self.assertEqual(tools.apple_sdk_name(FakeSettings('iOS', 'ios_fat')), 'iphoneos')
        self.assertEqual(tools.apple_sdk_name(FakeSettings('watchOS', 'ios_fat')), 'watchos')
        self.assertEqual(tools.apple_sdk_name(FakeSettings('tvOS', 'ios_fat')), 'appletvos')
        self.assertIsNone(tools.apple_sdk_name(FakeSettings('ConanOS', 'ios_fat')))

    def test_deployment_target_env_name(self):
        self.assertEqual(tools.apple_deployment_target_env('Macos', "10.1"),
                         {"MACOSX_DEPLOYMENT_TARGET": "10.1"})
        self.assertEqual(tools.apple_deployment_target_env('iOS', "10.1"),
                         {"IOS_DEPLOYMENT_TARGET": "10.1"})
        self.assertEqual(tools.apple_deployment_target_env('watchOS', "10.1"),
                         {"WATCHOS_DEPLOYMENT_TARGET": "10.1"})
        self.assertEqual(tools.apple_deployment_target_env('tvOS', "10.1"),
                         {"TVOS_DEPLOYMENT_TARGET": "10.1"})
        self.assertEqual(tools.apple_deployment_target_env('Linux', "10.1"), {})

    def test_deployment_target_flag_name(self):
        self.assertEqual(tools.apple_deployment_target_flag('Macos', "10.1"),
                         '-mmacosx-version-min=10.1')

        self.assertEqual(tools.apple_deployment_target_flag('Macos', "10.1", 'macosx'),
                         '-mmacosx-version-min=10.1')

        self.assertEqual(tools.apple_deployment_target_flag('iOS', "10.1"),
                         '-mios-version-min=10.1')

        self.assertEqual(tools.apple_deployment_target_flag('iOS', "10.1", 'iphoneos'),
                         '-mios-version-min=10.1')

        self.assertEqual(tools.apple_deployment_target_flag('iOS', "10.1", 'iphonesimulator'),
                         '-mios-simulator-version-min=10.1')

        self.assertEqual(tools.apple_deployment_target_flag('watchOS', "10.1"),
                         '-mwatchos-version-min=10.1')

        self.assertEqual(tools.apple_deployment_target_flag('watchOS', "10.1", 'watchos'),
                         '-mwatchos-version-min=10.1')

        self.assertEqual(tools.apple_deployment_target_flag('watchOS', "10.1", 'watchsimulator'),
                         '-mwatchos-simulator-version-min=10.1')

        self.assertEqual(tools.apple_deployment_target_flag('tvOS', "10.1"),
                         '-mtvos-version-min=10.1')

        self.assertEqual(tools.apple_deployment_target_flag('tvOS', "10.1", 'appletvos'),
                         '-mtvos-version-min=10.1')

        self.assertEqual(tools.apple_deployment_target_flag('tvOS', "10.1", 'appletvsimulator'),
                         '-mtvos-simulator-version-min=10.1')

        self.assertEqual(tools.apple_deployment_target_flag("Macos", "10.1", None, "catalyst"),
                         '-mios-version-min=10.1')

        self.assertEqual(tools.apple_deployment_target_flag("Macos", "10.1", "macosx", "catalyst"),
                         '-mios-version-min=10.1')

        self.assertEqual('', tools.apple_deployment_target_flag('Solaris', "10.1"))

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
        xcrun = tools.XCRun(settings)
        _common_asserts(xcrun)

        settings = FakeSettings('iOS', 'x86')
        xcrun = tools.XCRun(settings, sdk='macosx')
        _common_asserts(xcrun)
        # Simulator
        self.assertNotIn("iPhoneOS", xcrun.sdk_path)

        settings = FakeSettings('iOS', 'armv7')
        xcrun = tools.XCRun(settings)
        _common_asserts(xcrun)
        self.assertIn("iPhoneOS", xcrun.sdk_path)

        settings = FakeSettings('watchOS', 'armv7')
        xcrun = tools.XCRun(settings)
        _common_asserts(xcrun)
        self.assertIn("WatchOS", xcrun.sdk_path)

        # Default one
        settings = FakeSettings(None, None)
        xcrun = tools.XCRun(settings)
        _common_asserts(xcrun)
