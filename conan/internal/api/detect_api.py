import platform

from conans.util.runners import check_output_runner


def detect_os():
    the_os = platform.system()
    if the_os == "Darwin":
        the_os = "Macos"
    return the_os


def detect_architecture():
    # FIXME: Very weak check but not very common to run conan in other architectures
    machine = platform.machine()
    arch = None
    system = platform.system()

    # special detectors
    if system == "SunOS":
        arch = _get_solaris_architecture()
    elif system == "AIX":
        arch = _get_aix_architecture()
    if arch:
        return arch

    if "ppc64le" in machine:
        return "ppc64le"
    elif "ppc64" in machine:
        return "ppc64"
    elif "ppc" in machine:
        return "ppc32"
    elif "mips64" in machine:
        return "mips64"
    elif "mips" in machine:
        return "mips"
    elif "sparc64" in machine:
        return "sparcv9"
    elif "sparc" in machine:
        return "sparc"
    elif "aarch64" in machine:
        return "armv8"
    elif "arm64" in machine:
        return "armv8"
    elif "64" in machine:
        return "x86_64"
    elif "86" in machine:
        return "x86"
    elif "armv8" in machine:
        return "armv8"
    elif "armv7" in machine:
        return "armv7"
    elif "arm" in machine:
        return "armv6"
    elif "s390x" in machine:
        return "s390x"
    elif "s390" in machine:
        return "s390"
    elif "sun4v" in machine:
        return "sparc"
    elif "e2k" in machine:
        return _get_e2k_architecture()

    return None


def _get_solaris_architecture():
    # under intel solaris, platform.machine()=='i86pc' so we need to handle
    # it early to suport 64-bit
    processor = platform.processor()
    kernel_bitness, elf = platform.architecture()
    if "sparc" in processor:
        return "sparcv9" if kernel_bitness == "64bit" else "sparc"
    elif "i386" in processor:
        return "x86_64" if kernel_bitness == "64bit" else "x86"


def _get_aix_conf(options=None):
    options = " %s" % options if options else ""
    try:
        ret = check_output_runner("getconf%s" % options).strip()
        return ret
    except Exception:
        return None


def _get_aix_architecture():
    processor = platform.processor()
    if "powerpc" in processor:
        kernel_bitness = _get_aix_conf("KERNEL_BITMODE")
        if kernel_bitness:
            return "ppc64" if kernel_bitness == "64" else "ppc32"
    elif "rs6000" in processor:
        return "ppc32"


def _get_e2k_architecture():
    return {
        "E1C+": "e2k-v4",  # Elbrus 1C+ and Elbrus 1CK
        "E2C+": "e2k-v2",  # Elbrus 2CM
        "E2C+DSP": "e2k-v2",  # Elbrus 2C+
        "E2C3": "e2k-v6",  # Elbrus 2C3
        "E2S": "e2k-v3",  # Elbrus 2S (aka Elbrus 4C)
        "E8C": "e2k-v4",  # Elbrus 8C and Elbrus 8C1
        "E8C2": "e2k-v5",  # Elbrus 8C2 (aka Elbrus 8CB)
        "E12C": "e2k-v6",  # Elbrus 12C
        "E16C": "e2k-v6",  # Elbrus 16C
        "E32C": "e2k-v7",  # Elbrus 32C
    }.get(platform.processor())
