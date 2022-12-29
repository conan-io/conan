#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

from conans.util.runners import check_output_runner


def is_apple_os(os_):
    """returns True if OS is Apple one (Macos, iOS, watchOS or tvOS"""
    return str(os_) in ['Macos', 'iOS', 'watchOS', 'tvOS']


def to_apple_arch(arch):
    """converts conan-style architecture into Apple-style arch"""
    return {'x86': 'i386',
            'x86_64': 'x86_64',
            'armv7': 'armv7',
            'armv8': 'arm64',
            'armv8_32': 'arm64_32',
            'armv8.3': 'arm64e',
            'armv7s': 'armv7s',
            'armv7k': 'armv7k'}.get(str(arch))


def _guess_apple_sdk_name(os_, arch):
    if str(arch).startswith('x86'):
        return {'Macos': 'macosx',
                'iOS': 'iphonesimulator',
                'watchOS': 'watchsimulator',
                'tvOS': 'appletvsimulator'}.get(str(os_))
    else:
        return {'Macos': 'macosx',
                'iOS': 'iphoneos',
                'watchOS': 'watchos',
                'tvOS': 'appletvos'}.get(str(os_), None)


def apple_sdk_name(settings):
    """returns proper SDK name suitable for OS and architecture
    we're building for (considering simulators)"""
    arch = settings.get_safe('arch')
    os_ = settings.get_safe('os')
    os_sdk = settings.get_safe('os.sdk')
    return os_sdk or _guess_apple_sdk_name(os_, arch)


def apple_deployment_target_env(os_, os_version):
    """environment variable name which controls deployment target"""
    env_name = {'Macos': 'MACOSX_DEPLOYMENT_TARGET',
                'iOS': 'IOS_DEPLOYMENT_TARGET',
                'watchOS': 'WATCHOS_DEPLOYMENT_TARGET',
                'tvOS': 'TVOS_DEPLOYMENT_TARGET'}.get(str(os_))
    if not env_name:
        return {}
    return {env_name: os_version}


def apple_deployment_target_flag(os_, os_version, os_sdk=None, os_subsystem=None, arch=None):
    """compiler flag name which controls deployment target"""
    os_sdk = os_sdk if os_sdk else _guess_apple_sdk_name(os_, arch)
    flag = {'macosx': '-mmacosx-version-min',
            'iphoneos': '-mios-version-min',
            'iphonesimulator': '-mios-simulator-version-min',
            'watchos': '-mwatchos-version-min',
            'watchsimulator': '-mwatchos-simulator-version-min',
            'appletvos': '-mtvos-version-min',
            'appletvsimulator': '-mtvos-simulator-version-min'}.get(str(os_sdk))
    if os_subsystem == 'catalyst':
        # especial case, despite Catalyst is macOS, it requires an iOS version argument
        flag = '-mios-version-min'
    if not flag:
        return ''
    return "%s=%s" % (flag, os_version)


class XCRun(object):

    def __init__(self, settings, sdk=None):
        """sdk=False will skip the flag
           sdk=None will try to adjust it automatically"""
        if sdk is None and settings:
            sdk = apple_sdk_name(settings)
        self.sdk = sdk

    def _invoke(self, args):
        def cmd_output(cmd):
            return check_output_runner(cmd).strip()

        command = ['xcrun']
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
        """path to archive indexer (RANLIB)"""
        return self.find('ranlib')

    @property
    def strip(self):
        """path to symbol removal utility (STRIP)"""
        return self.find('strip')

    @property
    def libtool(self):
        """path to libtool"""
        return self.find('libtool')


def apple_dot_clean(folder):
    files = os.listdir(folder)
    for f in files:
        full_name = os.path.join(folder, f)
        if os.path.isdir(full_name):
            apple_dot_clean(full_name)
        elif f.startswith("._"):
            if os.path.exists(os.path.join(folder, f[2:])):
                os.remove(full_name)
