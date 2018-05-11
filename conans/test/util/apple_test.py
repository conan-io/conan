#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import platform
import os
from conans import tools


class FakeSettings(object):
    def __init__(self, _os, _arch):
        self._os = _os
        self._arch = _arch

    def get_safe(self, name):
        if name == 'os':
            return self._os
        elif name == 'arch':
            return self._arch


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
        self.assertEqual(tools.apple_deployment_target_flag('iOS', "10.1"),
                         '-mios-version-min=10.1')
        self.assertEqual(tools.apple_deployment_target_flag('watchOS', "10.1"),
                         '-mwatchos-version-min=10.1')
        self.assertEqual(tools.apple_deployment_target_flag('tvOS', "10.1"),
                         '-mappletvos-version-min=10.1')
        self.assertEqual('', tools.apple_deployment_target_flag('Solaris', "10.1"))

    @unittest.skipUnless(platform.system() == "Darwin", "Requires OSX")
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
