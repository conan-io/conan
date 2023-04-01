__all__ = [
    'b2_architecture',
    'b2_instruction_set',
    'b2_address_model',
    'b2_os',
    'b2_variant',
    'b2_cxxstd',
    'b2_cxxstd_dialect',
    'b2_toolset',
    'b2_path',
    'b2_features',
]


def b2_architecture(conan_arch):
    if not conan_arch:
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
    if not conan_arch:
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
    if not conan_arch:
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


def b2_os(conan_os):
    if not conan_os:
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
    else:
        return conan_os


def b2_variant(conan_build_type):
    if not conan_build_type:
        return None
    return conan_build_type.lower()


def b2_cxxstd(conan_cppstd):
    if not conan_cppstd:
        return None
    return conan_cppstd.replace('gnu', '') if conan_cppstd else None


def b2_cxxstd_dialect(conan_cppstd):
    if not conan_cppstd:
        return None
    if conan_cppstd and 'gnu' in conan_cppstd:
        return 'gnu'
    else:
        return None


def b2_toolset(conan_compiler, conan_compiler_version):
    if not conan_compiler:
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
