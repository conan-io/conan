import os
import platform
import re
import tempfile
import textwrap

from conan.api.output import ConanOutput
from conans.client.conf.detect_vs import latest_visual_studio_version_installed
from conans.model.version import Version
from conans.util.files import save
from conans.util.runners import detect_runner, check_output_runner


def _gcc_compiler(compiler_exe="gcc"):

    try:
        if platform.system() == "Darwin":
            # In Mac OS X check if gcc is a fronted using apple-clang
            _, out = detect_runner("%s --version" % compiler_exe)
            out = out.lower()
            if "clang" in out:
                return None

        ret, out = detect_runner('%s -dumpversion' % compiler_exe)
        if ret != 0:
            return None
        compiler = "gcc"
        installed_version = re.search(r"([0-9]+(\.[0-9])?)", out).group()
        # Since GCC 7.1, -dumpversion return the major version number
        # only ("7"). We must use -dumpfullversion to get the full version
        # number ("7.1.1").
        if installed_version:
            ConanOutput().success("Found %s %s" % (compiler, installed_version))
            return compiler, installed_version
    except Exception:
        return None


def _clang_compiler(compiler_exe="clang"):
    try:
        ret, out = detect_runner('%s --version' % compiler_exe)
        if ret != 0:
            return None
        if "Apple" in out:
            compiler = "apple-clang"
        elif "clang version" in out:
            compiler = "clang"
        installed_version = re.search(r"([0-9]+\.[0-9])", out).group()
        if installed_version:
            ConanOutput().success("Found %s %s" % (compiler, installed_version))
            return compiler, installed_version
    except Exception:
        return None


def _sun_cc_compiler(compiler_exe="cc"):
    try:
        _, out = detect_runner('%s -V' % compiler_exe)
        compiler = "sun-cc"
        installed_version = re.search(r"Sun C.*([0-9]+\.[0-9]+)", out)
        if installed_version:
            installed_version = installed_version.group(1)
        else:
            installed_version = re.search(r"([0-9]+\.[0-9]+)", out).group()
        if installed_version:
            ConanOutput().success("Found %s %s" % (compiler, installed_version))
            return compiler, installed_version
    except Exception:
        return None


def _get_default_compiler():
    """
    find the default compiler on the build machine
    search order and priority:
    1. CC and CXX environment variables are always top priority
    2. Visual Studio detection (Windows only) via vswhere or registry or environment variables
    3. Apple Clang (Mac only)
    4. cc executable
    5. gcc executable
    6. clang executable
    """
    output = ConanOutput()
    cc = os.environ.get("CC", "")
    cxx = os.environ.get("CXX", "")
    if cc or cxx:  # Env defined, use them
        output.info("CC and CXX: %s, %s " % (cc or "None", cxx or "None"))
        command = cc or cxx
        if "clang" in command.lower():
            return _clang_compiler(command)
        if "gcc" in command:
            gcc = _gcc_compiler(command)
            if platform.system() == "Darwin" and gcc is None:
                output.error("%s detected as a frontend using apple-clang. "
                             "Compiler not supported" % command)
            return gcc
        if platform.system() == "SunOS" and command.lower() == "cc":
            return _sun_cc_compiler(command)
        # I am not able to find its version
        output.error("Not able to automatically detect '%s' version" % command)
        return None

    vs = cc = sun_cc = None
    if platform.system() == "Windows":
        version = latest_visual_studio_version_installed()
        vs = ('msvc', version) if version else None

    gcc = _gcc_compiler()
    clang = _clang_compiler()
    if platform.system() == "SunOS":
        sun_cc = _sun_cc_compiler()

    if platform.system() == "Windows":
        return vs or cc or gcc or clang
    elif platform.system() == "Darwin":
        return clang or cc or gcc
    elif platform.system() == "SunOS":
        return sun_cc or cc or gcc or clang
    else:
        return cc or gcc or clang


def _get_profile_compiler_version(compiler, version):
    output = ConanOutput()
    tokens = version.main
    major = tokens[0]
    minor = tokens[1] if len(tokens) > 1 else 0
    if compiler == "clang" and major >= 8:
        output.info("clang>=8, using the major as version")
        return major
    elif compiler == "gcc" and major >= 5:
        output.info("gcc>=5, using the major as version")
        return major
    elif compiler == "apple-clang" and major >= 13:
        output.info("apple-clang>=13, using the major as version")
        return major
    elif compiler == "Visual Studio":
        return major
    elif compiler == "intel" and (major < 19 or (major == 19 and minor == 0)):
        return major
    elif compiler == "msvc":
        return major

    return version


def _detect_gcc_libcxx(version, executable):
    output = ConanOutput()
    # Assumes a working g++ executable
    if executable == "g++":  # we can rule out old gcc versions
        new_abi_available = version >= "5.1"
        if not new_abi_available:
            return "libstdc++"

    main = textwrap.dedent("""
        #include <string>

        using namespace std;
        static_assert(sizeof(std::string) != sizeof(void*), "using libstdc++");
        int main(){}
        """)
    t = tempfile.mkdtemp()
    filename = os.path.join(t, "main.cpp")
    save(filename, main)
    old_path = os.getcwd()
    os.chdir(t)
    try:
        error, out_str = detect_runner("%s main.cpp -std=c++11" % executable)
        if error:
            if "using libstdc++" in out_str:
                output.info("gcc C++ standard library: libstdc++")
                return "libstdc++"
            # Other error, but can't know, lets keep libstdc++11
            output.warning("compiler.libcxx check error: %s" % out_str)
            output.warning("Couldn't deduce compiler.libcxx for gcc>=5.1, assuming libstdc++11")
        else:
            output.info("gcc C++ standard library: libstdc++11")
        return "libstdc++11"
    finally:
        os.chdir(old_path)


def _detect_compiler_version(result):
    try:
        compiler, version = _get_default_compiler()
    except Exception:
        compiler, version = None, None
    if not compiler or not version:
        ConanOutput().info("No compiler was detected (one may not be needed)")
        return

    version = Version(version)

    result.append(("compiler", compiler))
    result.append(("compiler.version", _get_profile_compiler_version(compiler, version)))

    # Get compiler C++ stdlib
    if compiler == "apple-clang":
        result.append(("compiler.libcxx", "libc++"))
    elif compiler == "gcc":
        libcxx = _detect_gcc_libcxx(version, "g++")
        result.append(("compiler.libcxx", libcxx))
    elif compiler == "cc":
        if platform.system() == "SunOS":
            result.append(("compiler.libstdcxx", "libstdcxx4"))
    elif compiler == "clang":
        if platform.system() == "FreeBSD":
            result.append(("compiler.libcxx", "libc++"))
        else:
            if platform.system() == "Windows":
                # It could be LLVM/Clang with VS runtime or Msys2 with libcxx
                result.append(("compiler.runtime", "dynamic"))
                result.append(("compiler.runtime_type", "Release"))
                result.append(("compiler.runtime_version", "v143"))
                ConanOutput().warning("Assuming LLVM/Clang in Windows with VS 17 2022")
                ConanOutput().warning("If Msys2/Clang need to remove compiler.runtime* and "
                                      "define compiler.libcxx")
            else:
                libcxx = _detect_gcc_libcxx(version, "clang++")
                result.append(("compiler.libcxx", libcxx))
    elif compiler == "sun-cc":
        result.append(("compiler.libcxx", "libCstd"))
    elif compiler == "mcst-lcc":
        result.append(("compiler.libcxx", "libstdc++"))
    elif compiler == "msvc":
        # Add default mandatory fields for MSVC compiler
        result.append(("compiler.cppstd", "14"))
        result.append(("compiler.runtime", "dynamic"))
        result.append(("compiler.runtime_type", "Release"))

    if compiler != "msvc":
        cppstd = _cppstd_default(compiler, version)
        result.append(("compiler.cppstd", cppstd))


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


def _detected_architecture():
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


def _detect_os_arch(result):
    from conans.client.conf import get_default_settings_yml
    from conans.model.settings import Settings

    the_os = platform.system()
    if the_os == "Darwin":
        the_os = "Macos"
    result.append(("os", the_os))

    arch = _detected_architecture()

    if arch:
        if arch.startswith('arm'):
            settings = Settings.loads(get_default_settings_yml())
            defined_architectures = settings.arch.values_range
            defined_arm_architectures = [v for v in defined_architectures if v.startswith("arm")]

            for a in defined_arm_architectures:
                if arch.startswith(a):
                    arch = a
                    break
            else:
                ConanOutput().error("Your ARM '%s' architecture is probably not defined in "
                                    "settings.yml\n Please check your conan.conf and settings.yml "
                                    "files" % arch)

        result.append(("arch", arch))


def detect_defaults_settings():
    """ try to deduce current machine values without any constraints at all
    :return: A list with default settings
    """
    result = []
    _detect_os_arch(result)
    _detect_compiler_version(result)
    result.append(("build_type", "Release"))

    return result


def _cppstd_default(compiler, compiler_version):
    assert isinstance(compiler_version, Version)
    default = {"gcc": _gcc_cppstd_default(compiler_version),
               "clang": _clang_cppstd_default(compiler_version),
               "apple-clang": "gnu98",  # Confirmed in apple-clang 9.1 with a simple "auto i=1;"
               "msvc": _visual_cppstd_default(compiler_version),
               "mcst-lcc": _mcst_lcc_cppstd_default(compiler_version)}.get(str(compiler), None)
    return default


def _clang_cppstd_default(compiler_version):
    if compiler_version >= "16":
        return "gnu17"
    # Official docs are wrong, in 6.0 the default is gnu14 to follow gcc's choice
    return "gnu98" if compiler_version < "6" else "gnu14"


def _gcc_cppstd_default(compiler_version):
    if compiler_version >= "11":
        return "gnu17"
    return "gnu98" if compiler_version < "6" else "gnu14"


def _visual_cppstd_default(compiler_version):
    if compiler_version >= "190":  # VS 2015 update 3 only
        return "14"
    return None


def _intel_visual_cppstd_default(_):
    return None


def _intel_gcc_cppstd_default(_):
    return "gnu98"


def _mcst_lcc_cppstd_default(compiler_version):
    return "gnu14" if compiler_version >= "1.24" else "gnu98"
