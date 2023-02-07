__all__ = ["to_meson_machine", "to_meson_value", "to_cppstd_flag"]

# https://mesonbuild.com/Reference-tables.html#operating-system-names
_meson_system_map = {
    'Android': 'android',
    'Macos': 'darwin',
    'iOS': 'darwin',
    'watchOS': 'darwin',
    'tvOS': 'darwin',
    'FreeBSD': 'freebsd',
    'Emscripten': 'emscripten',
    'Linux': 'linux',
    'SunOS': 'sunos',
    'Windows': 'windows',
    'WindowsCE': 'windows',
    'WindowsStore': 'windows'
}

# https://mesonbuild.com/Reference-tables.html#cpu-families
_meson_cpu_family_map = {
    'armv4': ('arm', 'armv4', 'little'),
    'armv4i': ('arm', 'armv4i', 'little'),
    'armv5el': ('arm', 'armv5el', 'little'),
    'armv5hf': ('arm', 'armv5hf', 'little'),
    'armv6': ('arm', 'armv6', 'little'),
    'armv7': ('arm', 'armv7', 'little'),
    'armv7hf': ('arm', 'armv7hf', 'little'),
    'armv7s': ('arm', 'armv7s', 'little'),
    'armv7k': ('arm', 'armv7k', 'little'),
    'armv8': ('aarch64', 'armv8', 'little'),
    'armv8_32': ('aarch64', 'armv8_32', 'little'),
    'armv8.3': ('aarch64', 'armv8.3', 'little'),
    'avr': ('avr', 'avr', 'little'),
    'mips': ('mips', 'mips', 'big'),
    'mips64': ('mips64', 'mips64', 'big'),
    'ppc32be': ('ppc', 'ppc', 'big'),
    'ppc32': ('ppc', 'ppc', 'little'),
    'ppc64le': ('ppc64', 'ppc64', 'little'),
    'ppc64': ('ppc64', 'ppc64', 'big'),
    's390': ('s390', 's390', 'big'),
    's390x': ('s390x', 's390x', 'big'),
    'sh4le': ('sh4', 'sh4', 'little'),
    'sparc': ('sparc', 'sparc', 'big'),
    'sparcv9': ('sparc64', 'sparc64', 'big'),
    'wasm': ('wasm32', 'wasm32', 'little'),
    'x86': ('x86', 'x86', 'little'),
    'x86_64': ('x86_64', 'x86_64', 'little')
}

_vs_cppstd_map = {
    '14': "vc++14",
    '17': "vc++17",
    '20': "vc++latest"
}

_cppstd_map = {
    '98': "c++03", 'gnu98': "gnu++03",
    '11': "c++11", 'gnu11': "gnu++11",
    '14': "c++14", 'gnu14': "gnu++14",
    '17': "c++17", 'gnu17': "gnu++17",
    '20': "c++20", 'gnu20': "gnu++20"
}


def to_meson_machine(machine_os, machine_arch):
    """Gets the OS system info as the Meson machine context.

    :param machine_os: ``str`` OS name.
    :param machine_arch: ``str`` OS arch.
    :return: ``dict`` Meson machine context.
    """
    system = _meson_system_map.get(machine_os, machine_os.lower())
    default_cpu_tuple = (machine_arch.lower(), machine_arch.lower(), 'little')
    cpu_tuple = _meson_cpu_family_map.get(machine_arch, default_cpu_tuple)
    cpu_family, cpu, endian = cpu_tuple[0], cpu_tuple[1], cpu_tuple[2]
    context = {
        'system': system,
        'cpu_family': cpu_family,
        'cpu': cpu,
        'endian': endian,
    }
    return context


def to_meson_value(value):
    """Puts any value with a valid str-like Meson format.

    :param value: ``str``, ``bool``, or ``list``, otherwise, it will do nothing.
    :return: formatted value as a ``str``.
    """
    # https://mesonbuild.com/Machine-files.html#data-types
    if isinstance(value, str):
        return "'%s'" % value
    elif isinstance(value, bool):
        return 'true' if value else "false"
    elif isinstance(value, list):
        return '[%s]' % ', '.join([str(to_meson_value(val)) for val in value])
    return value


# FIXME: Move to another more common module
def to_cppstd_flag(compiler, cppstd):
    """Gets a valid cppstd flag.

    :param compiler: ``str`` compiler name.
    :param cppstd: ``str`` cppstd version.
    :return: ``str`` cppstd flag.
    """
    if compiler == "msvc":
        return _vs_cppstd_map.get(cppstd)
    else:
        return _cppstd_map.get(cppstd)
