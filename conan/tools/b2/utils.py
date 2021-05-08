from hashlib import md5
from conan.tools.microsoft.visual import msvc_version_to_vs_ide_version


def variation(conanfile):
    '''
    Returns a map of b2 features & values as translated from conan settings that
    can affect the link compatibility of libraries.
    '''
    result = {
        'toolset': _toolset(conanfile)
    }

    arch = conanfile.settings.get_safe('arch')

    result['architecture'] = {
        'x86': 'x86', 'x86_64': 'x86',
        'ppc64le': 'power', 'ppc64': 'power', 'ppc32': 'power', 'ppc32be': 'power',
        'armv4': 'arm', 'armv4i': 'arm',
        'armv5el': 'arm', 'armv5hf': 'arm',
        'armv6': 'arm', 'armv7': 'arm', 'armv7hf': 'arm', 'armv7s': 'arm', 'armv7k': 'arm',
        'armv8': 'arm', 'armv8_32': 'arm', 'armv8.3': 'arm',
        'sparc': 'sparc', 'sparcv9': 'sparc',
        'mips': 'mips1', 'mips64': 'mips64',
        's390': 's390', 's390x': 's390',
    }.get(arch)

    result['instruction-set'] = {
        'armv4': 'armv4',
        'armv6': 'armv6', 'armv7': 'armv7', 'armv7s': 'armv7s',
        'ppc64': 'powerpc64',
        'sparcv9': 'v9',
    }.get(arch)

    result['address-model'] = {
        'x86': '32', 'x86_64': '64',
        'ppc64le': '64', 'ppc64': '64', 'ppc32': '32', 'ppc32be': '32',
        'armv4': '32', 'armv4i': '32',
        'armv5el': '32', 'armv5hf': '32',
        'armv6': '32', 'armv7': '32', 'armv7s': '32', 'armv7k': '32', 'armv7hf': '32',
        'armv8': '64', 'armv8_32': '32', 'armv8.3': "64",
        'sparc': '32', 'sparcv9': '64',
        'mips': '32', 'mips64': '64',
        's390': '32', 's390x': '64',
    }.get(arch)

    result['target-os'] = {
        'Windows': 'windows', 'WindowsStore': 'windows', 'WindowsCE': 'windows',
        'Linux': 'linux',
        'Macos': 'darwin',
        'Android': 'android',
        'iOS': 'iphone',
        'watchOS': 'iphone',
        'tvOS': 'appletv',
        'FreeBSD': 'freebsd',
        'SunOS': 'solaris',
        'Arduino': 'linux',
        'AIX': 'aix',
        'VxWorks': 'vxworks',
    }.get(conanfile.settings.get_safe('os'))
    if result['target-os'] == 'windows' and conanfile.settings.get_safe('os.subsystem') == 'cygwin':
        result['target-os'] = 'cygwin'

    result['variant'] = {
        'Debug': 'debug',
        'Release': 'release',
        'RelWithDebInfo': 'relwithdebinfo',
        'MinSizeRel': 'minsizerel',
    }.get(conanfile.settings.get_safe('build_type'))

    cppstd = conanfile.settings.get_safe('compiler.cppstd')
    cppstd = cppstd or conanfile.settings.get_safe('cppstd')

    result['cxxstd'] = {
        '98': '98', 'gnu98': '98',
        '11': '11', 'gnu11': '11',
        '14': '14', 'gnu14': '14',
        '17': '17', 'gnu17': '17',
        '20': '20', 'gnu20': '20',
        '23': '23', 'gnu23': '23',
        '26': '26', 'gnu26': '26',
        '2a': '2a', 'gnu2a': '2a',
        '2b': '2b', 'gnu2b': '2b',
        '2c': '2c', 'gnu2c': '2c',
    }.get(cppstd)

    if cppstd and cppstd.startswith('gnu'):
        result['cxxstd:dialect'] = 'gnu'

    libcxx = conanfile.settings.get_safe('compiler.libcxx')
    if libcxx:
        stdlibs = {
            'libstdc++': 'gnu',
            'libstdc++11': 'gnu11',
            'libc++': 'libc++',
        }
        if conanfile.settings.get_safe('compiler') == 'sun-cc':
            stdlibs.update(
                libstdcxx='apache',
                libstlport='sun-stlport'
            )
        result['stdlib'] = stdlibs.get(libcxx)

    threads = conanfile.settings.get_safe('compiler.threads')
    if threads:
        result['threadapi'] = {
            'posix': 'pthread',
            'win32': 'win32',
        }.get(threads)

    runtime = conanfile.settings.get_safe('compiler.runtime')
    if runtime:
        result['runtime-link'] = {
            'static': 'static',
            'MT': 'static',
            'MTd': 'static',
            'dynamic': 'shared',
            'MD': 'shared',
            'MDd': 'shared',
        }.get(runtime)
        result['runtime-debugging'] = {
            'Debug': 'on',
            'MTd': 'on',
            'MDd': 'on',
            'Release': 'off',
            'MT': 'off',
            'MD': 'off',
        }.get(conanfile.settings.get_safe('compiler.runtime_type') or runtime)

    link = conanfile.options.get_safe('shared')
    if link is not None:
        result['link'] = 'shared' if link else 'static'

    return result


def _toolset(conanfile):
    compiler = conanfile.settings.get_safe('compiler')
    toolset = {
        'sun-cc': 'sun',
        'gcc': 'gcc',
        'Visual Studio': 'msvc',
        'msvc': 'msvc',
        'clang': 'clang',
        'apple-clang': 'clang'
    }.get(compiler)

    if not toolset:
        return

    if toolset == 'msvc':
        visual_studio_version = str(conanfile.settings.compiler.version)
        if compiler == 'msvc':
            visual_studio_version = msvc_version_to_vs_ide_version(visual_studio_version)
        version = {
            "15": "14.1",
            "16": "14.2",
            "17": "14.3",
        }.get(visual_studio_version) or (visual_studio_version + '.0')
    else:
        version = str(conanfile.settings.get_safe('compiler.version'))
    return toolset + '-' + version


def variation_id(variation):
    """
    A compact single comma separated list of the variation where only the values
    of the b2 variation are included in sorted by feature name order.
    """
    return ",".join((i[1] for i in _nonempty_items(variation)))


def variation_key(variation_id):
    """
    A hashed key of the variation to use a UID for the variation.
    """
    return md5(variation_id.encode('utf-8')).hexdigest()


def properties(variations):
    """
    Generates a b2 requirements list, i.e. <name>value list, from the given 'variations' dict.
    """
    return ['<%s>%s' % (k, v) for k, v in _nonempty_items(variations)]


def jamify(s):
    """
    Convert a valid Python identifier to a string that follows b2
    identifier convention.
    """
    return s.lower().replace("_", "-")


def _nonempty_items(variation):
    return (i for i in sorted(variation.items()) if i[1])
