import pytest
from mock import Mock

from conan.tools.b2 import utils as b2_utils
from conans import ConanFile, Settings
from conans.client.conf import get_default_settings_yml
from conans.model.conf import Conf
from conans.model.env_info import EnvValues


def test_variation():
    # empty settings
    conanfile = ConanFile(Mock(), None)
    conanfile.initialize(Settings({}), EnvValues())

    variation = b2_utils.variation(conanfile)
    assert variation == {
        'target-os': None,
        'toolset': None,
        'architecture': None,
        'instruction-set': None,
        'address-model': None,
        'variant': None,
        'cxxstd': None,
    }

    settings = Settings.loads(get_default_settings_yml())
    settings.os = 'Android'
    settings.compiler = 'gcc'
    settings.compiler.version = '6.3'
    settings.compiler.cppstd = 'gnu17'
    settings.compiler.libcxx = 'libstdc++11'
    settings.arch = 'x86'
    settings.build_type = 'Release'
    conanfile.settings = settings

    variation = b2_utils.variation(conanfile)
    assert variation == {
        'target-os': 'android',
        'toolset': 'gcc-6.3',
        'architecture': 'x86',
        'instruction-set': None,
        'address-model': '32',
        'variant': 'release',
        'cxxstd': '17',
        'cxxstd:dialect': 'gnu',
        'stdlib': 'gnu11',
    }

    # os
    for settings_os in ['Windows', 'WindowsStore', 'WindowsCE']:
        conanfile.settings.os = settings_os
        variation = b2_utils.variation(conanfile)
        assert variation['target-os'] == 'windows'

    for settings_os in ['iOS', 'watchOS']:
        conanfile.settings.os = settings_os
        variation = b2_utils.variation(conanfile)
        assert variation['target-os'] == 'iphone'

    for settings_os in ['Linux', 'Arduino']:
        conanfile.settings.os = settings_os
        variation = b2_utils.variation(conanfile)
        assert variation['target-os'] == 'linux'

    conanfile.settings.os = 'Windows'
    conanfile.settings.os.subsystem = 'cygwin'
    variation = b2_utils.variation(conanfile)
    assert variation['target-os'] == 'cygwin'

    conanfile.settings.os = 'Macos'
    variation = b2_utils.variation(conanfile)
    assert variation['target-os'] == 'darwin'

    conanfile.settings.os = 'tvOS'
    variation = b2_utils.variation(conanfile)
    assert variation['target-os'] == 'appletv'

    conanfile.settings.os = 'Android'
    variation = b2_utils.variation(conanfile)
    assert variation['target-os'] == 'android'

    conanfile.settings.os = 'FreeBSD'
    variation = b2_utils.variation(conanfile)
    assert variation['target-os'] == 'freebsd'

    conanfile.settings.os = 'SunOS'
    variation = b2_utils.variation(conanfile)
    assert variation['target-os'] == 'solaris'

    # compiler
    conanfile.settings.compiler.version = '9.2'
    variation = b2_utils.variation(conanfile)
    assert variation['toolset'] == 'gcc-9.2'

    conanfile.settings.compiler = 'sun-cc'
    conanfile.settings.compiler.version = '5.12'
    variation = b2_utils.variation(conanfile)
    assert variation['toolset'] == 'sun-5.12'

    conanfile.settings.compiler = 'Visual Studio'
    conanfile.settings.compiler.version = '12'
    variation = b2_utils.variation(conanfile)
    assert variation['toolset'] == 'msvc-12.0'

    conanfile.settings.compiler = 'Visual Studio'
    conanfile.settings.compiler.version = '15'
    variation = b2_utils.variation(conanfile)
    assert variation['toolset'] == 'msvc-14.1'

    conanfile.settings.compiler.version = '17'
    variation = b2_utils.variation(conanfile)
    assert variation['toolset'] == 'msvc-14.3'

    conanfile.settings.compiler = 'msvc'
    conanfile.settings.compiler.version = '170'
    variation = b2_utils.variation(conanfile)
    assert variation['toolset'] == 'msvc-11.0'

    conanfile.settings.compiler = 'msvc'
    conanfile.settings.compiler.version = '193'
    variation = b2_utils.variation(conanfile)
    assert variation['toolset'] == 'msvc-14.3'

    conanfile.settings.compiler = 'clang'
    conanfile.settings.compiler.version = '3.8'
    variation = b2_utils.variation(conanfile)
    assert variation['toolset'] == 'clang-3.8'

    conanfile.settings.compiler = 'apple-clang'
    conanfile.settings.compiler.version = '11.0'
    variation = b2_utils.variation(conanfile)
    assert variation['toolset'] == 'clang-11.0'

    # arch
    conanfile.settings.arch = 'x86_64'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 'x86'
    assert variation['instruction-set'] == None
    assert variation['address-model'] == '64'

    conanfile.settings.arch = 'x86_64'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 'x86'
    assert variation['instruction-set'] == None
    assert variation['address-model'] == '64'

    conanfile.settings.arch = 'ppc32'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 'power'
    assert variation['instruction-set'] == None
    assert variation['address-model'] == '32'

    conanfile.settings.arch = 'ppc32be'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 'power'
    assert variation['instruction-set'] == None
    assert variation['address-model'] == '32'

    conanfile.settings.arch = 'ppc64le'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 'power'
    assert variation['instruction-set'] == None
    assert variation['address-model'] == '64'

    conanfile.settings.arch = 'ppc64'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 'power'
    assert variation['instruction-set'] == 'powerpc64'
    assert variation['address-model'] == '64'

    conanfile.settings.arch = 'armv4'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 'arm'
    assert variation['instruction-set'] == 'armv4'
    assert variation['address-model'] == '32'

    conanfile.settings.arch = 'armv6'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 'arm'
    assert variation['instruction-set'] == 'armv6'
    assert variation['address-model'] == '32'

    conanfile.settings.arch = 'armv7'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 'arm'
    assert variation['instruction-set'] == 'armv7'
    assert variation['address-model'] == '32'

    conanfile.settings.arch = 'armv7s'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 'arm'
    assert variation['instruction-set'] == 'armv7s'
    assert variation['address-model'] == '32'

    for arch in ['armv8', 'armv8.3']:
        conanfile.settings.arch = arch
        variation = b2_utils.variation(conanfile)
        assert variation['architecture'] == 'arm'
        assert variation['instruction-set'] == None
        assert variation['address-model'] == '64'

    for arch in ['armv4i', 'armv5el', 'armv5hf', 'armv7hf', 'armv7k', 'armv8_32']:
        conanfile.settings.arch = arch
        variation = b2_utils.variation(conanfile)
        assert variation['architecture'] == 'arm'
        assert variation['instruction-set'] == None
        assert variation['address-model'] == '32'

    conanfile.settings.arch = 'sparc'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 'sparc'
    assert variation['instruction-set'] == None
    assert variation['address-model'] == '32'

    conanfile.settings.arch = 'sparcv9'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 'sparc'
    assert variation['instruction-set'] == 'v9'
    assert variation['address-model'] == '64'

    conanfile.settings.arch = 'mips'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 'mips1'
    assert variation['instruction-set'] == None
    assert variation['address-model'] == '32'

    conanfile.settings.arch = 'mips64'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 'mips64'
    assert variation['instruction-set'] == None
    assert variation['address-model'] == '64'

    conanfile.settings.arch = 's390'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 's390'
    assert variation['instruction-set'] == None
    assert variation['address-model'] == '32'

    conanfile.settings.arch = 's390x'
    variation = b2_utils.variation(conanfile)
    assert variation['architecture'] == 's390'
    assert variation['instruction-set'] == None
    assert variation['address-model'] == '64'

    # build_type
    conanfile.settings.build_type = 'Debug'
    variation = b2_utils.variation(conanfile)
    assert variation['variant'] == 'debug'

    conanfile.settings.build_type = 'RelWithDebInfo'
    variation = b2_utils.variation(conanfile)
    assert variation['variant'] == 'relwithdebinfo'

    conanfile.settings.build_type = 'MinSizeRel'
    variation = b2_utils.variation(conanfile)
    assert variation['variant'] == 'minsizerel'

    # cppstd
    for cxxstd in ['98', '11', '14', '17', '20', '23']:
        conanfile.settings.cppstd = cxxstd
        variation = b2_utils.variation(conanfile)
        assert variation['cxxstd'] == cxxstd
        assert variation.get('cxxstd:dialect') == None

        conanfile.settings.cppstd = 'gnu' + cxxstd
        variation = b2_utils.variation(conanfile)
        assert variation['cxxstd'] == cxxstd
        assert variation['cxxstd:dialect'] == 'gnu'

    # libcxx
    conanfile.settings.compiler = 'sun-cc'
    conanfile.settings.compiler.libcxx = 'libstdc++'
    variation = b2_utils.variation(conanfile)
    assert variation['stdlib'] == 'gnu'

    conanfile.settings.compiler.libcxx = 'libstdcxx'
    variation = b2_utils.variation(conanfile)
    assert variation['stdlib'] == 'apache'

    conanfile.settings.compiler.libcxx = 'libstlport'
    variation = b2_utils.variation(conanfile)
    assert variation['stdlib'] == 'sun-stlport'

    conanfile.settings.compiler = 'gcc'
    conanfile.settings.compiler.libcxx = 'libstdc++'
    variation = b2_utils.variation(conanfile)
    assert variation['stdlib'] == 'gnu'

    conanfile.settings.compiler.libcxx = 'libstdc++11'
    variation = b2_utils.variation(conanfile)
    assert variation['stdlib'] == 'gnu11'

    conanfile.settings.compiler = 'clang'
    conanfile.settings.compiler.libcxx = 'libstdc++11'
    variation = b2_utils.variation(conanfile)
    assert variation['stdlib'] == 'gnu11'

    conanfile.settings.compiler.libcxx = 'libc++'
    variation = b2_utils.variation(conanfile)
    assert variation['stdlib'] == 'libc++'

    # compiler.threads
    conanfile.settings.os = 'Windows'
    conanfile.settings.compiler = 'gcc'
    conanfile.settings.compiler.threads = 'posix'
    variation = b2_utils.variation(conanfile)
    assert variation['threadapi'] == 'pthread'

    conanfile.settings.compiler.threads = 'win32'
    variation = b2_utils.variation(conanfile)
    assert variation['threadapi'] == 'win32'

    # compiler.runtime and compiler.runtime_type
    conanfile.settings.os = 'Windows'
    conanfile.settings.compiler = 'msvc'
    conanfile.settings.compiler.runtime = 'static'
    conanfile.settings.compiler.runtime_type = 'Debug'
    variation = b2_utils.variation(conanfile)
    assert variation['runtime-debugging'] == 'on'
    assert variation['runtime-link'] == 'static'

    conanfile.settings.compiler.runtime = 'dynamic'
    variation = b2_utils.variation(conanfile)
    assert variation['runtime-debugging'] == 'on'
    assert variation['runtime-link'] == 'shared'

    conanfile.settings.compiler.runtime_type = 'Release'
    variation = b2_utils.variation(conanfile)
    assert variation['runtime-debugging'] == 'off'
    assert variation['runtime-link'] == 'shared'

    conanfile.settings.compiler.runtime = 'static'
    variation = b2_utils.variation(conanfile)
    assert variation['runtime-debugging'] == 'off'
    assert variation['runtime-link'] == 'static'

    conanfile.settings.compiler = 'Visual Studio'
    conanfile.settings.compiler.runtime = 'MT'
    variation = b2_utils.variation(conanfile)
    assert variation['runtime-debugging'] == 'off'
    assert variation['runtime-link'] == 'static'

    conanfile.settings.compiler.runtime = 'MTd'
    variation = b2_utils.variation(conanfile)
    assert variation['runtime-debugging'] == 'on'
    assert variation['runtime-link'] == 'static'

    conanfile.settings.compiler.runtime = 'MDd'
    variation = b2_utils.variation(conanfile)
    assert variation['runtime-debugging'] == 'on'
    assert variation['runtime-link'] == 'shared'

    conanfile.settings.compiler.runtime = 'MD'
    variation = b2_utils.variation(conanfile)
    assert variation['runtime-debugging'] == 'off'
    assert variation['runtime-link'] == 'shared'

    conanfile = ConanFile(Mock(), None)
    conanfile.options = {
        "shared": [True, False],
    }
    conanfile.initialize(Settings({}), EnvValues())

    conanfile.options.shared = False
    variation = b2_utils.variation(conanfile)
    assert variation['link'] == 'static'

    conanfile.options.shared = True
    variation = b2_utils.variation(conanfile)
    assert variation['link'] == 'shared'

def test_variation_id():
    # empty settings
    conanfile = ConanFile(Mock(), None)
    conanfile.initialize(Settings({}), EnvValues())

    variation = b2_utils.variation(conanfile)
    variation_id = b2_utils.variation_id(variation)
    assert variation_id == ''

    settings = Settings.loads(get_default_settings_yml())
    settings.os = 'Linux'
    settings.compiler = 'gcc'
    settings.compiler.version = '6.3'
    settings.compiler.cppstd = 'gnu17'
    settings.arch = 'x86'
    settings.build_type = 'Release'
    conanfile.settings = settings

    variation = b2_utils.variation(conanfile)
    variation_id = b2_utils.variation_id(variation)
    assert variation_id == '32,x86,17,gnu,linux,gcc-6.3,release'


def test_variation_key():
    # empty settings
    conanfile = ConanFile(Mock(), None)
    conanfile.initialize(Settings({}), EnvValues())

    variation = b2_utils.variation(conanfile)
    variation_id = b2_utils.variation_id(variation)
    variation_key = b2_utils.variation_key(variation_id)
    assert variation_key == 'd41d8cd98f00b204e9800998ecf8427e'

    settings = Settings.loads(get_default_settings_yml())
    settings.os = 'Linux'
    settings.compiler = 'gcc'
    settings.compiler.version = '6.3'
    settings.compiler.cppstd = 'gnu17'
    settings.arch = 'x86'
    settings.build_type = 'Release'
    conanfile.settings = settings

    variation = b2_utils.variation(conanfile)
    variation_id = b2_utils.variation_id(variation)
    variation_key = b2_utils.variation_key(variation_id)
    assert variation_key == '316f2f0b155dc874a672d40d98d93f95'


def test_properties():
    # empty settings
    conanfile = ConanFile(Mock(), None)
    conanfile.initialize(Settings({}), EnvValues())
    settings = Settings.loads(get_default_settings_yml())
    settings.os = 'Linux'
    settings.compiler = 'gcc'
    settings.compiler.version = '6.3'
    settings.arch = 'x86'
    settings.build_type = 'Release'
    settings.cppstd = 'gnu17'
    conanfile.settings = settings

    variation = b2_utils.variation(conanfile)
    properties = b2_utils.properties(variation)
    assert properties == [
        '<address-model>32',
        '<architecture>x86',
        '<cxxstd>17',
        '<cxxstd:dialect>gnu',
        '<target-os>linux',
        '<toolset>gcc-6.3',
        '<variant>release',
    ]

def test_jamify():
    assert b2_utils.jamify('Foo_Bar') == 'foo-bar'
