#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess


def is_apple_os(_os):
    """returns True if OS is Apple one (Macos, iOS, watchOS or tvOS"""
    return str(_os) in ['Macos', 'iOS', 'watchOS', 'tvOS']


def to_apple_arch(arch):
    """converts conan-style architecture into Apple-style arch"""
    return {'x86': 'i386',
            'x86_64': 'x86_64',
            'armv7': 'armv7',
            'armv8': 'arm64',
            'armv7s': 'armv7s',
            'armv7k': 'armv7k'}.get(str(arch))


def apple_sdk_name(settings):
    """returns proper SDK name suitable for OS and architecture
    we're building for (considering simulators)"""
    arch = settings.get_safe('arch')
    _os = settings.get_safe('os')
    if str(arch).startswith('x86'):
        return {'Macos': 'macosx',
                'iOS': 'iphonesimulator',
                'watchOS': 'watchsimulator',
                'tvOS': 'appletvsimulator'}.get(str(_os))
    elif str(arch).startswith('arm'):
        return {'iOS': 'iphoneos',
                'watchOS': 'watchos',
                'tvOS': 'appletvos'}.get(str(_os))
    else:
        return None


def apple_deployment_target_env_name(_os):
    """environment variable name which controls deployment target"""
    return {'Macos': 'MACOSX_DEPLOYMENT_TARGET',
            'iOS': 'IOS_DEPLOYMENT_TARGET',
            'watchOS': 'WATCHOS_DEPLOYMENT_TARGET',
            'tvOS': 'TVOS_DEPLOYMENT_TARGET'}.get(str(_os))


def apple_deployment_target_flag_name(_os):
    """compiler flag name which controls deployment target"""
    return {'Macos': '-mmacosx-version-min',
            'iOS': '-mios-version-min',
            'watchOS': '-mwatchos-version-min',
            'tvOS': '-mappletvos-version-min'}.get(str(_os))


class XCRun(object):

    def __init__(self, sdk=None):
        self.sdk = sdk

    def _invoke(self, args):
        def cmd_output(cmd):
            return subprocess.check_output(cmd).decode().strip()

        command = ['xcrun', '-find']
        if self.sdk:
            command.extend(['-sdk', self.sdk])
        command.extend(args)
        return cmd_output(command)

    def find(self, tool):
        """find SDK tools (e.g. clang, ar, ranlib, lipo, codesign, etc.)"""
        return self._invoke(['--find', tool])

    @property
    def sdk_path(self):
        """obtain sdk path (aka apple sysroot or -isysroot"""
        return self._invoke(['--show-sdk-path'])

    @property
    def sdk_version(self):
        """obtain sdk version"""
        return self._invoke(['--show-sdk-version'])

    @property
    def sdk_platform_path(self):
        """obtain sdk platform path"""
        return self._invoke(['--show-sdk-platform-path'])

    @property
    def sdk_platform_version(self):
        """obtain sdk platform version"""
        return self._invoke(['--show-sdk-platform-version'])

    @property
    def cc(self):
        """path to C compiler (CC)"""
        return self.find('clang')

    @property
    def cxx(self):
        """path to C++ compiler (CXX)"""
        return self.find('clang++')

    @property
    def ar(self):
        """path to archiver (AR)"""
        return self.find('ar')

    @property
    def ranlib(self):
        """path to archive indexer (RANBLI)"""
        return self.find('ranlib')

    @property
    def strip(self):
        """path to symbol removal utility (STRIP)"""
        return self.find('strip')
