import os
import platform
import re

from conan.api.output import ConanOutput
from conan.internal.api.detect_api import detect_os, detect_architecture, default_msvc_runtime, \
    detect_libcxx, default_cppstd
from conans.client.conf.detect_vs import latest_visual_studio_version_installed
from conans.model.version import Version
from conans.util.runners import detect_runner


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


def _msvc_cl_compiler(compiler_exe="cl"):
    try:
        compiler_exe = compiler_exe.strip('"')
        ret, out = detect_runner(f'"{compiler_exe}" /?')
        if ret != 0:
            return None
        first_line = out.splitlines()[0]
        if not "Microsoft" in first_line:
            return None
        compiler = "msvc"
        version_regex = re.search(r"(?P<major>[0-9]+)\.(?P<minor>[0-9]+)\.([0-9]+)\.?([0-9]+)?", first_line)
        if not version_regex:
            return None
        # 19.36.32535 -> 193
        version = f"{version_regex.group('major')}{version_regex.group('minor')[0]}"
        return (compiler, version)
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
        if "gcc" in command or "g++" in command or "c++" in command:
            gcc = _gcc_compiler(command)
            if platform.system() == "Darwin" and gcc is None:
                output.error("%s detected as a frontend using apple-clang. "
                             "Compiler not supported" % command)
            return gcc
        if platform.system() == "SunOS" and command.lower() == "cc":
            return _sun_cc_compiler(command)
        if platform.system() == "Windows" and command.rstrip('"').endswith(("cl", "cl.exe")) and not "clang" in command:
            return _msvc_cl_compiler(command)

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
    elif platform.system() in ["Darwin", "FreeBSD"]:
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
    elif compiler == "intel" and (major < 19 or (major == 19 and minor == 0)):
        return major
    elif compiler == "msvc":
        return major

    return version


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

    runtime, runtime_version = default_msvc_runtime(compiler)
    if runtime:
        result.append(("compiler.runtime", runtime))
    if runtime_version:
        result.append(("compiler.runtime_version", runtime_version))
    libcxx = detect_libcxx(compiler, version)
    if libcxx:
        result.append(("compiler.libcxx", libcxx))
    cppstd = default_cppstd(compiler, version)
    if cppstd:
        result.append(("compiler.cppstd", cppstd))


def detect_defaults_settings():
    """ try to deduce current machine values without any constraints at all
    :return: A list with default settings
    """
    result = []
    the_os = detect_os()
    result.append(("os", the_os))

    arch = detect_architecture()
    if arch:
        result.append(("arch", arch))
    _detect_compiler_version(result)
    result.append(("build_type", "Release"))
    return result
