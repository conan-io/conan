from conans.errors import ConanException
from hashlib import md5
from base64 import b32encode

__all__ = [
    'b2_address_model',
    'b2_architecture',
    'b2_cxxstd_dialect',
    'b2_cxxstd',
    'b2_features',
    'b2_instruction_set',
    'b2_link',
    'b2_os',
    'b2_path',
    'b2_runtime_debugging',
    'b2_runtime_link',
    'b2_threadapi',
    'b2_toolset',
    'b2_variant',
    'b2_variation_id',
    'b2_variation_key',
    'b2_variation',
]


def b2_architecture(conan_arch):
    if conan_arch is None:
        return None
    elif conan_arch.startswith('x86'):
        return 'x86'
    elif conan_arch.startswith('ppc'):
        return 'power'
    elif conan_arch.startswith('arm'):
        return 'arm'
    elif conan_arch.startswith('sparc'):
        return 'sparc'
    elif conan_arch.startswith('mips'):
        return conan_arch
    else:
        return None


def b2_instruction_set(conan_arch):
    if conan_arch is None:
        return None
    elif conan_arch.startswith('armv6'):
        return 'armv6'
    elif conan_arch.startswith('armv7'):
        return 'armv7'
    elif conan_arch.startswith('armv7s'):
        return 'armv7s'
    elif conan_arch.startswith('sparcv9'):
        return 'v9'
    else:
        return None


def b2_address_model(conan_arch):
    if conan_arch is None:
        return None
    elif '32' in conan_arch:
        return '32'
    elif '64' in conan_arch:
        return '64'
    elif conan_arch in ['x86', 'mips']:
        return '32'
    elif conan_arch in ['sparcv9']:
        return '64'
    elif conan_arch.startswith('arm'):
        if conan_arch.startswith('armv8'):
            return '64'
        else:
            return '32'
    elif conan_arch.startswith('sparc'):
        return '32'
    else:
        return None


def b2_os(conan_os, conan_os_subsystem=None):
    if conan_os is None:
        return None
    conan_os = conan_os.lower()
    if conan_os.startswith('windows'):
        return 'windows'
    elif conan_os in ['macos', 'ios', 'watchos', 'tvos']:
        return 'darwin'
    elif conan_os == 'subos':
        return 'solaris'
    elif conan_os in ['arduino']:
        return 'linux'
    elif conan_os == 'windows' and conan_os_subsystem == 'cygwin':
        return 'cygwin'
    else:
        return conan_os


def b2_variant(conan_build_type):
    if conan_build_type is None:
        return None
    return conan_build_type.lower()


def b2_cxxstd(conan_cppstd):
    if conan_cppstd is None:
        return None
    return conan_cppstd.replace('gnu', '') if conan_cppstd else None


def b2_cxxstd_dialect(conan_cppstd):
    if conan_cppstd is None:
        return None
    if conan_cppstd and 'gnu' in conan_cppstd:
        return 'gnu'
    else:
        return None


def b2_toolset(conan_compiler, conan_compiler_version):
    if conan_compiler is None:
        return None
    toolset = conan_compiler.lower()
    if 'clang' in conan_compiler:
        toolset = 'clang'
    elif 'sun-cc' == conan_compiler:
        toolset = 'sun'
    elif 'Visual Studio' == conan_compiler:
        toolset = 'msvc'
    elif 'intel' in conan_compiler:
        toolset = 'intel'
    if not conan_compiler_version:
        return toolset
    version = conan_compiler_version
    if toolset == 'msvc':
        if conan_compiler_version == '15':
            version = '14.1'
        else:
            version = conan_compiler_version + '.0'
    return toolset + '-' + version


def b2_path(path):
    """
    Adjust a regular path to the form b2 can use in source code.
    """
    return path.replace('\\', '/')


def b2_features(features):
    """
    Generate a b2 requirements list, i.e. <name>value list, from the given
    'features' dict.
    """
    result = []
    for k, v in sorted(features.items()):
        if v:
            result += ['<%s>%s' % (k, v)]
    return result


def b2_threadapi(conan_compiler_threads):
    if conan_compiler_threads is None:
        return None
    conan_compiler_threads = conan_compiler_threads.lower()
    if conan_compiler_threads == 'posix':
        return 'pthread'


def b2_runtime_link(conan_compiler_runtime):
    if conan_compiler_runtime is None:
        return None
    if conan_compiler_runtime in ['static', 'MT', 'MTd']:
        return 'static'
    return 'shared'


def b2_runtime_debugging(conan_compiler_runtime):
    if conan_compiler_runtime is None:
        return None
    if conan_compiler_runtime in ['Debug', 'MTd', 'MDd']:
        return 'on'
    return 'off'


def b2_link(conan_options_shared):
    if conan_options_shared is None:
        return None
    if conan_options_shared:
        return 'shared'
    return 'static'


def _get_setting(settings, name, default=None, optional=True):
    result = settings.get_safe(name, default) if settings else None
    if not result and not optional:
        raise ConanException(
            "Need 'settings.{}', but it is not defined.".format(name))
    return result


def _get_option(options, name, default=None, optional=True):
    result = options.get_safe(name, default) if options else None
    if not result and not optional:
        raise ConanException(
            "Need 'options.{}', but it is not defined.".format(name))
    return result


def b2_variation(settings, options=None):
    """
    Returns a map of b2 features & values as translated from conan settings
    and options that can affect the link compatibility of libraries.
    """
    _b2_variation_v = {
        'toolset': b2_toolset(
            _get_setting(settings, "compiler"),
            _get_setting(settings, "compiler.version")),
        'architecture': b2_architecture(
            _get_setting(settings, "arch")),
        'instruction-set': b2_instruction_set(
            _get_setting(settings, "arch")),
        'address-model': b2_address_model(
            _get_setting(settings, "arch")),
        'target-os': b2_os(
            _get_setting(settings, "os"),
            _get_setting(settings, "os.subsystem")),
        'variant': b2_variant(
            _get_setting(settings, "build_type")),
        'cxxstd': b2_cxxstd(
            _get_setting(settings, "cppstd")),
        'cxxstd:dialect': b2_cxxstd_dialect(
            _get_setting(settings, "cppstd")),
        'threadapi': b2_threadapi(
            _get_setting(settings, 'compiler.threads')),
        'runtime-link': b2_runtime_link(
            _get_setting(settings, 'compiler.runtime')),
        'runtime-debugging': b2_runtime_debugging(
            _get_setting(settings, 'compiler.runtime_type')),
        'link': b2_link(
            _get_option(options, 'shared')),
    }
    return _b2_variation_v


def b2_variation_id(settings, options=None):
    """
    A compact single comma separated list of the variation are included in
    sorted by feature name order.
    """
    vid = []
    _b2_variation = b2_variation(settings, options)
    for k in sorted(_b2_variation.keys()):
        if _b2_variation[k] is not None:
            vid += [k+'='+_b2_variation[k]]
    return ",".join(vid)


def b2_variation_key(settings, options=None):
    """
    A hashed key of the variation to use a UID for the variation.
    """
    return b32encode(md5(b2_variation_id(settings, options).encode('utf-8')).digest()).decode('utf-8').lower().replace('=', '')
