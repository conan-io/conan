import os
import platform
import re
from subprocess import PIPE, Popen, STDOUT

from conans.client.output import Color
from conans.client.tools.win import latest_visual_studio_version_installed
from conans.client.tools import detected_os
from conans.model.version import Version


def _execute(command):
    proc = Popen(command, shell=True, bufsize=1, stdout=PIPE, stderr=STDOUT)

    output_buffer = []
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        # output.write(line)
        output_buffer.append(str(line))

    proc.communicate()
    return proc.returncode, "".join(output_buffer)


def _gcc_compiler(output, compiler_exe="gcc"):

    try:
        if platform.system() == "Darwin":
            # In Mac OS X check if gcc is a fronted using apple-clang
            _, out = _execute("%s --version" % compiler_exe)
            out = out.lower()
            if "clang" in out:
                return None

        ret, out = _execute('%s -dumpversion' % compiler_exe)
        if ret != 0:
            return None
        compiler = "gcc"
        installed_version = re.search("([0-9](\.[0-9])?)", out).group()
        # Since GCC 7.1, -dumpversion return the major version number
        # only ("7"). We must use -dumpfullversion to get the full version
        # number ("7.1.1").
        if installed_version:
            output.success("Found %s %s" % (compiler, installed_version))
            major = installed_version.split(".")[0]
            if int(major) >= 5:
                output.info("gcc>=5, using the major as version")
                installed_version = major
            return compiler, installed_version
    except:
        return None


def _clang_compiler(output, compiler_exe="clang"):
    try:
        ret, out = _execute('%s --version' % compiler_exe)
        if ret != 0:
            return None
        if "Apple" in out:
            compiler = "apple-clang"
        elif "clang version" in out:
            compiler = "clang"
        installed_version = re.search("([0-9]+\.[0-9])", out).group()
        if installed_version:
            output.success("Found %s %s" % (compiler, installed_version))
            major = installed_version.split(".")[0]
            if int(major) >= 8 and compiler == "clang":
                output.info("clang>=8, using the major as version")
                installed_version = major
            return compiler, installed_version
    except:
        return None


def _sun_cc_compiler(output, compiler_exe="cc"):
    try:
        _, out = _execute('%s -V' % compiler_exe)
        compiler = "sun-cc"
        installed_version = re.search("([0-9]+\.[0-9]+)", out).group()
        if installed_version:
            output.success("Found %s %s" % (compiler, installed_version))
            return compiler, installed_version
    except:
        return None


def _get_default_compiler(output):
    cc = os.environ.get("CC", "")
    cxx = os.environ.get("CXX", "")
    if cc or cxx:  # Env defined, use them
        output.info("CC and CXX: %s, %s " % (cc or "None", cxx or "None"))
        command = cc or cxx
        if "gcc" in command:
            gcc = _gcc_compiler(output, command)
            if platform.system() == "Darwin" and gcc is None:
                output.error(
                    "%s detected as a frontend using apple-clang. Compiler not supported" % command
                )
            return gcc
        if "clang" in command.lower():
            return _clang_compiler(output, command)
        if platform.system() == "SunOS" and command.lower() == "cc":
            return _sun_cc_compiler(output, command)
        # I am not able to find its version
        output.error("Not able to automatically detect '%s' version" % command)
        return None

    if detected_os() == "Windows":
        version = latest_visual_studio_version_installed(output)
        vs = ('Visual Studio', version) if version else None
    gcc = _gcc_compiler(output)
    clang = _clang_compiler(output)
    if platform.system() == "SunOS":
        sun_cc = _sun_cc_compiler(output)

    if detected_os() == "Windows":
        return vs or gcc or clang
    elif platform.system() == "Darwin":
        return clang or gcc
    elif platform.system() == "SunOS":
        return sun_cc or gcc or clang
    else:
        return gcc or clang


def _detect_compiler_version(result, output, profile_path):
    try:
        compiler, version = _get_default_compiler(output)
    except:
        compiler, version = None, None
    if not compiler or not version:
        output.error("Unable to find a working compiler")
    else:
        result.append(("compiler", compiler))
        result.append(("compiler.version", version))
        if compiler == "apple-clang":
            result.append(("compiler.libcxx", "libc++"))
        elif compiler == "gcc":
            result.append(("compiler.libcxx", "libstdc++"))
            if Version(version) >= Version("5.1"):
                profile_name = os.path.basename(profile_path)
                msg = """
Conan detected a GCC version > 5 but has adjusted the 'compiler.libcxx' setting to
'libstdc++' for backwards compatibility.
Your compiler is likely using the new CXX11 ABI by default (libstdc++11).

If you want Conan to use the new ABI, edit the {profile} profile at:

    {profile_path}

adjusting 'compiler.libcxx=libstdc++11'
""".format(profile=profile_name, profile_path=profile_path)
                output.writeln("\n************************* WARNING: GCC OLD ABI COMPATIBILITY "
                               "***********************\n %s\n************************************"
                               "************************************************\n\n\n" % msg,
                               Color.BRIGHT_RED)
        elif compiler == "cc":
            if platform.system() == "SunOS":
                result.append(("compiler.libstdcxx", "libstdcxx4"))
        elif compiler == "clang":
            if platform.system() == "FreeBSD":
                result.append(("compiler.libcxx", "libc++"))
            else:
                result.append(("compiler.libcxx", "libstdc++"))
        elif compiler == "sun-cc":
            result.append(("compiler.libcxx", "libCstd"))


def _detect_os_arch(result, output):
    architectures = {'i386': 'x86',
                     'i686': 'x86',
                     'i86pc': 'x86',
                     'amd64': 'x86_64',
                     'aarch64': 'armv8',
                     'sun4v': 'sparc'}
    the_os = detected_os()
    result.append(("os", the_os))
    result.append(("os_build", the_os))
    platform_machine = platform.machine().lower()
    if platform_machine:
        arch = architectures.get(platform_machine, platform_machine)
        if arch.startswith('arm'):
            for a in ("armv6", "armv7hf", "armv7", "armv8"):
                if arch.startswith(a):
                    arch = a
                    break
            else:
                output.error("Your ARM '%s' architecture is probably not defined in settings.yml\n"
                             "Please check your conan.conf and settings.yml files" % arch)
        result.append(("arch", arch))
        result.append(("arch_build", arch))


def detect_defaults_settings(output, profile_path):
    """ try to deduce current machine values without any constraints at all
    :param output: Conan Output instance
    :param profile_path: Conan profile file path
    :return: A list with default settings
    """
    result = []
    _detect_os_arch(result, output)
    _detect_compiler_version(result, output, profile_path)
    result.append(("build_type", "Release"))

    return result
