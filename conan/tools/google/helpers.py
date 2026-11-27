import json

# Conan settings.os -> @platforms//os:<value>
# https://github.com/bazelbuild/platforms/blob/main/os/BUILD
_BAZEL_OS = {
    "Linux": "linux",
    "Macos": "macos",
    "iOS": "ios",
    "tvOS": "tvos",
    "watchOS": "watchos",
    "visionOS": "visionos",
    "Windows": "windows",
    "WindowsStore": "windows",
    "WindowsCE": "windows",
    "Android": "android",
    "FreeBSD": "freebsd",
    "OpenBSD": "openbsd",
    "NetBSD": "netbsd",
    "Emscripten": "emscripten",
    "Neutrino": "qnx",
    "VxWorks": "vxworks",
    "baremetal": "none",
    "Arduino": "none",
}

# Conan settings.arch -> @platforms//cpu:<value>
# https://github.com/bazelbuild/platforms/blob/main/cpu/BUILD
_BAZEL_CPU = {
    "x86": "x86_32",
    "x86_64": "x86_64",
    "armv8": "aarch64",
    "armv8.3": "arm64e",
    "arm64ec": "aarch64",
    "armv8_32": "arm64_32",
    "armv7": "armv7",
    "armv7hf": "armv7",
    "armv7k": "armv7k",
    "armv5el": "arm",
    "armv5hf": "arm",
    "armv6": "arm",
    "ppc32": "ppc32",
    "ppc64le": "ppc64le",
    "ppc64": "ppc",
    "s390x": "s390x",
    "riscv32": "riscv32",
    "riscv64": "riscv64",
    "mips64": "mips64",
    "wasm": "wasm32",
    "wasm64": "wasm64",
}


def to_bazel_os_constraint(os_):
    """
    :return: ``@platforms//os:xxxx`` label for the given Conan ``settings.os`` value or ``None``
    """
    value = _BAZEL_OS.get(str(os_)) if os_ else None
    return f"@platforms//os:{value}" if value else None


def to_bazel_cpu_constraint(arch):
    """
    :return: ``@platforms//cpu:xxxx`` label for the given Conan ``settings.arch`` value or ``None``
    """
    value = _BAZEL_CPU.get(str(arch)) if arch else None
    return f"@platforms//cpu:{value}" if value else None


def to_bazel_compiler(compiler):
    """
    Value used as ``compiler`` field in the ``cc_toolchain_config``. Bazel uses it to select
    some default behaviors and users can ``select()`` on it via
    ``@bazel_tools//tools/cpp:compiler``.
    """
    return {"apple-clang": "clang"}.get(compiler, compiler)


def to_starlark(value, indent=8):
    """
    Converts a Python built-in value into its Starlark representation.
    Lists and dicts are rendered one item per line to keep the BUILD files readable.
    """
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    if isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        pad = " " * indent
        items = "".join(f"{pad}{to_starlark(v, indent + 4)},\n" for v in value)
        return f"[\n{items}{' ' * (indent - 4)}]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        pad = " " * indent
        items = "".join(f"{pad}{json.dumps(str(k))}: {to_starlark(v, indent + 4)},\n"
                        for k, v in value.items())
        return f"{{\n{items}{' ' * (indent - 4)}}}"
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value))
