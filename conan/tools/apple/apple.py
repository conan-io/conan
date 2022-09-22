#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

from conans.util.runners import check_output_runner
from conans.client.tools.apple import to_apple_arch as _to_apple_arch


def is_apple_os(conanfile):
    """returns True if OS is Apple one (Macos, iOS, watchOS or tvOS"""
    os_ = conanfile.settings.get_safe("os")
    return str(os_) in ['Macos', 'iOS', 'watchOS', 'tvOS']


def to_apple_arch(conanfile):
    """converts conan-style architecture into Apple-style arch"""
    arch_ = conanfile.settings.get_safe("arch")
    return _to_apple_arch(arch_)


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
    os_sdk_version = settings.get_safe('os.sdk_version') or ""
    return "{}{}".format(os_sdk, os_sdk_version) if os_sdk else _guess_apple_sdk_name(os_, arch)


def apple_min_version_flag(conanfile):
    """compiler flag name which controls deployment target"""
    os_version = conanfile.settings.get_safe("os.version")
    if not os_version:
        return ''

    os_ = conanfile.settings.get_safe("os")
    os_sdk = conanfile.settings.get_safe("os.sdk")
    os_subsystem = conanfile.settings.get_safe("os.subsystem")
    arch = conanfile.settings.get_safe("arch")

    if not os_version:
        return ''
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


def apple_sdk_path(conanfile):
    sdk_path = conanfile.conf.get("tools.apple:sdk_path")
    if not sdk_path:
        sdk_path = XCRun(conanfile.settings).sdk_path
    return sdk_path


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


def fix_apple_shared_install_name(conanfile):

    def _get_install_name(path_to_dylib):
        command = "otool -D {}".format(path_to_dylib)
        install_name = check_output_runner(command).strip().split(":")[1].strip()
        return install_name

    def _osx_collect_dylibs(lib_folder):
        return [os.path.join(full_folder, f) for f in os.listdir(lib_folder) if f.endswith(".dylib")
                and not os.path.islink(os.path.join(lib_folder, f))]

    def _fix_install_name(dylib_path, new_name):
        command = f"install_name_tool {dylib_path} -id {new_name}"
        conanfile.run(command)

    def _fix_dep_name(dylib_path, old_name, new_name):
        command = f"install_name_tool {dylib_path} -change {old_name} {new_name}"
        conanfile.run(command)

    substitutions = {}

    if is_apple_os(conanfile) and conanfile.options.get_safe("shared", False):
        libdirs = getattr(conanfile.cpp.package, "libdirs")
        for libdir in libdirs:
            full_folder = os.path.join(conanfile.package_folder, libdir)
            shared_libs = _osx_collect_dylibs(full_folder)
            # fix LC_ID_DYLIB in first pass
            for shared_lib in shared_libs:
                install_name = _get_install_name(shared_lib)
                rpath_name = f"@rpath/{os.path.basename(install_name)}"
                _fix_install_name(shared_lib, rpath_name)
                substitutions[install_name] = rpath_name

            # fix dependencies in second pass
            for shared_lib in shared_libs:
                for old, new in substitutions.items():
                    _fix_dep_name(shared_lib, old, new)
