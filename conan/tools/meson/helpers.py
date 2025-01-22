from conan.api.output import ConanOutput
from conan.tools.build.flags import cppstd_msvc_flag
from conan.internal.model.options import _PackageOption

__all__ = ["to_meson_machine", "to_meson_value", "to_cppstd_flag", "to_cstd_flag"]

# https://mesonbuild.com/Reference-tables.html#operating-system-names
_meson_system_map = {
    'Android': 'android',
    'Macos': 'darwin',
    'iOS': 'darwin',
    'watchOS': 'darwin',
    'tvOS': 'darwin',
    'visionOS': 'darwin',
    'FreeBSD': 'freebsd',
    'Emscripten': 'emscripten',
    'Linux': 'linux',
    'SunOS': 'sunos',
    'Windows': 'windows',
    'WindowsCE': 'windows',
    'WindowsStore': 'windows',
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
    'arm64ec': ('aarch64', 'arm64ec', 'little'),
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
    'x86_64': ('x86_64', 'x86_64', 'little'),
    'riscv32': ('riscv32', 'riscv32', 'little'),
    'riscv64': ('riscv64', 'riscv32', 'little')
}


# Meson valid values
# "none", "c++98", "c++03", "c++11", "c++14", "c++17", "c++1z", "c++2a", "c++20",
# "gnu++11", "gnu++14", "gnu++17", "gnu++1z", "gnu++2a", "gnu++20"
_cppstd_map = {
    '98': "c++98", 'gnu98': "c++98",
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
    # we don't need to transform the integer values
    if isinstance(value, str):
        return f"'{value}'"
    elif isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, list):
        return '[{}]'.format(', '.join([str(to_meson_value(val)) for val in value]))
    elif isinstance(value, _PackageOption):
        ConanOutput().warning(f"Please, do not use a Conan option value directly. "
                              f"Convert 'options.{value.name}' into a valid Python"
                              f"data type, e.g, bool(self.options.shared)", warn_tag="deprecated")
    return value


# FIXME: Move to another more common module
def to_cppstd_flag(compiler, compiler_version, cppstd):
    """Gets a valid cppstd flag.

    :param compiler: ``str`` compiler name.
    :param compiler_version: ``str`` compiler version.
    :param cppstd: ``str`` cppstd version.
    :return: ``str`` cppstd flag.
    """
    if compiler == "msvc":
        # Meson's logic with 'vc++X' vs 'c++X' is possibly a little outdated.
        # Presumably the intent is 'vc++X' is permissive and 'c++X' is not,
        # but '/permissive-' is the default since 16.8.
        flag = cppstd_msvc_flag(compiler_version, cppstd)
        return 'v%s' % flag if flag else None
    else:
        return _cppstd_map.get(cppstd)


def to_cstd_flag(cstd):
    """ possible values
    none, c89, c99, c11, c17, c18, c2x, c23, gnu89, gnu99, gnu11, gnu17, gnu18, gnu2x, gnu23
    """
    _cstd_map = {
        '99': "c99",
        '11': "c11",
        '17': "c17",
        '23': "c23",
    }
    return _cstd_map.get(cstd, cstd)
