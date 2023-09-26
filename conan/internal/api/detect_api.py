import os
import platform
import re
import tempfile
import textwrap

from conan.api.output import ConanOutput
from conans.model.version import Version
from conans.util.files import save
from conans.util.runners import check_output_runner, detect_runner


def detect_os():
    the_os = platform.system()
    if the_os == "Darwin":
        the_os = "Macos"
    return the_os


def detect_arch():
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
    elif "ARM64" in machine:
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
    except Exception as e:
        ConanOutput(scope="detect_api").warning(f"Couldn't get aix getconf {e}")
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


def detect_libcxx(compiler, version):
    assert isinstance(version, Version)

    def _detect_gcc_libcxx(version_, executable):
        output = ConanOutput(scope="detect_api")
        # Assumes a working g++ executable
        if executable == "g++":  # we can rule out old gcc versions
            new_abi_available = version_ >= "5.1"
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

        # This is not really a detection in most cases
        # Get compiler C++ stdlib

    if compiler == "apple-clang":
        return "libc++"
    elif compiler == "gcc":
        libcxx = _detect_gcc_libcxx(version, "g++")
        return libcxx
    elif compiler == "cc":
        if platform.system() == "SunOS":
            return "libstdcxx4"
    elif compiler == "clang":
        if platform.system() == "FreeBSD":
            return "libc++"
        elif platform.system() == "Darwin":
            return "libc++"
        elif platform.system() == "Windows":
            return  # by default windows will assume LLVM/Clang with VS backend
        else:  # Linux
            libcxx = _detect_gcc_libcxx(version, "clang++")
            return libcxx
    elif compiler == "sun-cc":
        return "libCstd"
    elif compiler == "mcst-lcc":
        return "libstdc++"


def default_msvc_runtime(compiler):
    if platform.system() != "Windows":
        return None, None
    if compiler == "clang":
        # It could be LLVM/Clang with VS runtime or Msys2 with libcxx
        ConanOutput(scope="detect_api").warning("Assuming LLVM/Clang in Windows with VS 17 2022")
        ConanOutput(scope="detect_api").warning("If Msys2/Clang need to remove compiler.runtime* "
                                                "and define compiler.libcxx")
        return "dynamic", "v143"
    elif compiler == "msvc":
        # Add default mandatory fields for MSVC compiler
        return "dynamic", None
    return None, None


def default_cppstd(compiler, compiler_version):
    """ returns the default cppstd for the compiler-version. This is not detected, just the default
    """
    def _clang_cppstd_default(version):
        if version >= "16":
            return "gnu17"
        # Official docs are wrong, in 6.0 the default is gnu14 to follow gcc's choice
        return "gnu98" if version < "6" else "gnu14"

    def _gcc_cppstd_default(version):
        if version >= "11":
            return "gnu17"
        return "gnu98" if version < "6" else "gnu14"

    def _visual_cppstd_default(version):
        if version >= "190":  # VS 2015 update 3 only
            return "14"
        return None

    def _mcst_lcc_cppstd_default(version):
        return "gnu14" if version >= "1.24" else "gnu98"

    default = {"gcc": _gcc_cppstd_default(compiler_version),
               "clang": _clang_cppstd_default(compiler_version),
               "apple-clang": "gnu98",
               "msvc": _visual_cppstd_default(compiler_version),
               "mcst-lcc": _mcst_lcc_cppstd_default(compiler_version)}.get(str(compiler), None)
    return default


def detect_compiler():
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
    output = ConanOutput(scope="detect_api")
    cc = os.environ.get("CC", "")
    cxx = os.environ.get("CXX", "")
    if cc or cxx:  # Env defined, use them
        output.info("CC and CXX: %s, %s " % (cc or "None", cxx or "None"))
        command = cc or cxx
        if "clang" in command.lower():
            return _clang_compiler(command)
        if "gcc" in command or "g++" in command or "c++" in command:
            gcc, gcc_version = _gcc_compiler(command)
            if platform.system() == "Darwin" and gcc is None:
                output.error("%s detected as a frontend using apple-clang. "
                             "Compiler not supported" % command)
            return gcc, gcc_version
        if platform.system() == "SunOS" and command.lower() == "cc":
            return _sun_cc_compiler(command)
        if platform.system() == "Windows" and command.rstrip('"').endswith(("cl", "cl.exe")) \
                and "clang" not in command:
            return _msvc_cl_compiler(command)

        # I am not able to find its version
        output.error("Not able to automatically detect '%s' version" % command)
        return None, None

    if platform.system() == "Windows":
        version = _detect_vs_ide_version()
        version = {"17": "193", "16": "192", "15": "191"}.get(str(version))  # Map to compiler
        if version:
            return 'msvc', Version(version)

    if platform.system() == "SunOS":
        sun_cc, sun_cc_version = _sun_cc_compiler()
        if sun_cc:
            return sun_cc, sun_cc_version

    if platform.system() in ["Darwin", "FreeBSD"]:
        clang, clang_version = _clang_compiler()  # prioritize clang
        if clang:
            return clang, clang_version
        return
    else:
        gcc, gcc_version = _gcc_compiler()
        if gcc:
            return gcc, gcc_version
        return _clang_compiler()


def default_msvc_ide_version(version):
    version = {"193": "17", "192": "16", "191": "15"}.get(str(version))
    if version:
        return Version(version)


def _detect_vs_ide_version():
    from conans.client.conf.detect_vs import vs_installation_path
    msvc_versions = "17", "16", "15"
    for version in msvc_versions:
        vs_path = os.getenv('vs%s0comntools' % version)
        path = vs_path or vs_installation_path(version)
        if path:
            ConanOutput(scope="detect_api").info("Found msvc %s" % version)
            return Version(version)
    return None


def _gcc_compiler(compiler_exe="gcc"):
    try:
        if platform.system() == "Darwin":
            # In Mac OS X check if gcc is a fronted using apple-clang
            _, out = detect_runner("%s --version" % compiler_exe)
            out = out.lower()
            if "clang" in out:
                return None, None

        ret, out = detect_runner('%s -dumpversion' % compiler_exe)
        if ret != 0:
            return None, None
        compiler = "gcc"
        installed_version = re.search(r"([0-9]+(\.[0-9])?)", out).group()
        # Since GCC 7.1, -dumpversion return the major version number
        # only ("7"). We must use -dumpfullversion to get the full version
        # number ("7.1.1").
        if installed_version:
            ConanOutput(scope="detect_api").info("Found %s %s" % (compiler, installed_version))
            return compiler, Version(installed_version)
    except (Exception,):  # to disable broad-except
        return None, None


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
            ConanOutput(scope="detect_api").info("Found %s %s" % (compiler, installed_version))
            return compiler, Version(installed_version)
    except (Exception,):  # to disable broad-except
        return None, None


def _clang_compiler(compiler_exe="clang"):
    try:
        ret, out = detect_runner('%s --version' % compiler_exe)
        if ret != 0:
            return None, None
        if "Apple" in out:
            compiler = "apple-clang"
        elif "clang version" in out:
            compiler = "clang"
        else:
            return None, None
        installed_version = re.search(r"([0-9]+\.[0-9])", out).group()
        if installed_version:
            ConanOutput(scope="detect_api").info("Found %s %s" % (compiler, installed_version))
            return compiler, Version(installed_version)
    except (Exception,):  # to disable broad-except
        return None, None


def _msvc_cl_compiler(compiler_exe="cl"):
    """ only if CC/CXX env-vars are defined pointing to cl.exe, and the VS environment must
    be active to have them in the path
    """
    try:
        compiler_exe = compiler_exe.strip('"')
        ret, out = detect_runner(f'"{compiler_exe}" /?')
        if ret != 0:
            return None, None
        first_line = out.splitlines()[0]
        if "Microsoft" not in first_line:
            return None, None
        compiler = "msvc"
        version_regex = re.search(r"(?P<major>[0-9]+)\.(?P<minor>[0-9]+)\.([0-9]+)\.?([0-9]+)?",
                                  first_line)
        if not version_regex:
            return None, None
        # 19.36.32535 -> 193
        version = f"{version_regex.group('major')}{version_regex.group('minor')[0]}"
        return compiler, Version(version)
    except (Exception,):  # to disable broad-except
        return None, None


def default_compiler_version(compiler, version):
    """ returns the default version that Conan uses in profiles, typically dropping some
    of the minor or patch digits, that do not affect binary compatibility
    """
    output = ConanOutput(scope="detect_api")
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
    elif compiler == "intel" and (major < 19 or (major == 19 and minor == 0)):
        return major
    elif compiler == "msvc":
        return major
    return version
