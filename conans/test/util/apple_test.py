#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import platform
import os
from nose.plugins.attrib import attr
from conans import tools


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
        class FakeSettings(object):
            def __init__(self, _os, _arch):
                self._os = _os
                self._arch = _arch

            def get_safe(self, name):
                if name == 'os':
                    return self._os
                elif name == 'arch':
                    return self._arch

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
        self.assertEqual(tools.apple_deployment_target_env_name('Macos'), 'MACOSX_DEPLOYMENT_TARGET')
        self.assertEqual(tools.apple_deployment_target_env_name('iOS'), 'IOS_DEPLOYMENT_TARGET')
        self.assertEqual(tools.apple_deployment_target_env_name('watchOS'), 'WATCHOS_DEPLOYMENT_TARGET')
        self.assertEqual(tools.apple_deployment_target_env_name('tvOS'), 'TVOS_DEPLOYMENT_TARGET')
        self.assertIsNone(tools.apple_deployment_target_env_name('Linux'))

    def test_deployment_target_flag_name(self):
        self.assertEqual(tools.apple_deployment_target_flag_name('Macos'), '-mmacosx-version-min')
        self.assertEqual(tools.apple_deployment_target_flag_name('iOS'), '-mios-version-min')
        self.assertEqual(tools.apple_deployment_target_flag_name('watchOS'), '-mwatchos-version-min')
        self.assertEqual(tools.apple_deployment_target_flag_name('tvOS'), '-mappletvos-version-min')
        self.assertIsNone(tools.apple_deployment_target_flag_name('Solaris'))

    @attr('darwin')
    def test_xcrun(self):
        if platform.system() != "Darwin":
            return
        xcrun = tools.XCRun('macosx')
        self.assertTrue(xcrun.cc.endswith('clang'))
        self.assertTrue(xcrun.cxx.endswith('clang++'))
        self.assertTrue(xcrun.ar.endswith('ar'))
        self.assertTrue(xcrun.ranlib.endswith('ranlib'))
        self.assertTrue(xcrun.strip.endswith('strip'))

        self.assertTrue(os.path.isdir(xcrun.sdk_path))

        xcrun = tools.XCRun()
        self.assertTrue(xcrun.find('lipo').endswith('lipo'))
