#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

import pytest

from conan.tools.apple.apple import _to_apple_arch, apple_min_version_flag, \
    is_apple_os
from conan.test.utils.mocks import MockSettings, ConanFileMock


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
                             [("Macos", "10.1", "macosx", None, '-mmacosx-version-min=10.1'),
                              ("iOS", "10.1", "iphoneos", None, '-mios-version-min=10.1'),
                              ("iOS", "10.1", "iphonesimulator", None,
                               '-mios-simulator-version-min=10.1'),
                              ("watchOS", "10.1", "watchos", None, '-mwatchos-version-min=10.1'),
                              ("watchOS", "10.1", "watchsimulator", None,
                               '-mwatchos-simulator-version-min=10.1'),
                              ("tvOS", "10.1", "appletvos", None, '-mtvos-version-min=10.1'),
                              ("tvOS", "10.1", "appletvsimulator", None,
                               '-mtvos-simulator-version-min=10.1'),
                              ("Macos", "10.1", "macosx", "catalyst", '-mios-version-min=10.1'),
                              ("Solaris", "10.1", None, None, ''),
                              ("Macos", "10.1", None, None, '-mmacosx-version-min=10.1'),
                              ("Macos", None, "macosx", None, '')
                              ])
    def test_deployment_target_flag_name(self, os_, version, sdk, subsystem, flag):
        conanfile = ConanFileMock()
        settings = MockSettings({"os": os_,
                                 "os.version": version,
                                 "os.sdk": sdk,
                                 "os.subsystem": subsystem})
        conanfile.settings = settings
        assert apple_min_version_flag(conanfile) == flag


class AppleTest(unittest.TestCase):

    def test_is_apple_os(self):
        # FIXME: parametrize!
        apple_os = ['iOS', 'tvOS', 'watchOS', 'Macos']
        non_apple_os = ['Windows', 'Linux', 'Android']
        conanfile = ConanFileMock()
        for os_ in apple_os:
            settings = MockSettings({"os": os_})
            conanfile.settings = settings
            self.assertTrue(is_apple_os(conanfile))
        for os_ in non_apple_os:
            settings = MockSettings({"os": os_})
            conanfile.settings = settings
            self.assertFalse(is_apple_os(conanfile))

    def test_to_apple_arch(self):
        self.assertEqual(_to_apple_arch('x86'), 'i386')
        self.assertEqual(_to_apple_arch('x86_64'), 'x86_64')
        self.assertEqual(_to_apple_arch('armv7'), 'armv7')
        self.assertEqual(_to_apple_arch('armv7s'), 'armv7s')
        self.assertEqual(_to_apple_arch('armv7k'), 'armv7k')
        self.assertEqual(_to_apple_arch('armv8'), 'arm64')
        self.assertEqual(_to_apple_arch('armv8.3'), 'arm64e')
        self.assertEqual(_to_apple_arch('armv8_32'), 'arm64_32')
        self.assertIsNone(_to_apple_arch('mips'))
        self.assertEqual(_to_apple_arch('mips', default='mips'), 'mips')
