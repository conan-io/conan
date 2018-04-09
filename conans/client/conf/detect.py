import os
import platform
import re
from subprocess import Popen, PIPE, STDOUT

from conans.client.output import Color
from conans.model.version import Version
from conans.tools import vs_installation_path


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

        _, out = _execute('%s -dumpversion' % compiler_exe)
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
        _, out = _execute('%s --version' % compiler_exe)
        if "Apple" in out:
            compiler = "apple-clang"
        elif "clang version" in out:
            compiler = "clang"
        installed_version = re.search("([0-9]\.[0-9])", out).group()
        if installed_version:
            output.success("Found %s %s" % (compiler, installed_version))
            return compiler, installed_version
    except:
        return None


def _visual_compiler_cygwin(output, version):
    if os.path.isfile("/proc/registry/HKEY_LOCAL_MACHINE/SOFTWARE/Microsoft/Windows/CurrentVersion/ProgramFilesDir (x86)"):
        is_64bits = True
    else:
        is_64bits = False

    if is_64bits:
        key_name = r'HKEY_LOCAL_MACHINE\SOFTWARE\Wow6432Node\Microsoft\VisualStudio\SxS\VC7'
    else:
        key_name = r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\VisualStudio\SxS\VC7'

    if not os.path.isfile("/proc/registry/" + key_name.replace('\\', '/') + "/" + version):
        return None

    installed_version = Version(version).major(fill=False)
    compiler = "Visual Studio"
    output.success("CYGWIN: Found %s %s" % (compiler, installed_version))
    return compiler, installed_version


def _visual_compiler(output, version):
    'version have to be 8.0, or 9.0 or... anything .0'
    if platform.system().startswith("CYGWIN"):
        return _visual_compiler_cygwin(output, version)

    if version == "15":
        vs_path = os.getenv('vs150comntools')
        path = vs_path or vs_installation_path("15")
        if path:
            compiler = "Visual Studio"
            output.success("Found %s %s" % (compiler, "15"))
            return compiler, "15"
        return None

    version = "%s.0" % version
    from six.moves import winreg  # @UnresolvedImport
    try:
        hKey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                              r"SOFTWARE\Microsoft\Windows\CurrentVersion")
        winreg.QueryValueEx(hKey, "ProgramFilesDir (x86)")
        is_64bits = True
    except EnvironmentError:
        is_64bits = False
    finally:
        winreg.CloseKey(hKey)

    if is_64bits:
        key_name = r'SOFTWARE\Wow6432Node\Microsoft\VisualStudio\SxS\VC7'
    else:
        key_name = r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\VisualStudio\SxS\VC7'

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_name)
        winreg.QueryValueEx(key, version)

        installed_version = Version(version).major(fill=False)
        compiler = "Visual Studio"
        output.success("Found %s %s" % (compiler, installed_version))
        return compiler, installed_version
    except EnvironmentError:
        return None


def _visual_compiler_last(output):
    last_version = None
    for version in ["8", "9", "10", "11", "12", "14", "15"]:
        vs = _visual_compiler(output, version)
        last_version = vs or last_version
    return last_version


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
        vs = _visual_compiler_last(output)
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


def _detect_compiler_version(result, output):
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

                msg = """
Conan detected a GCC version > 5 but has adjusted the 'compiler.libcxx' setting to
'libstdc++' for backwards compatibility.
Your compiler is likely using the new CXX11 ABI by default (libstdc++11).

If you want Conan to use the new ABI, edit the default profile at:

    ~/.conan/profiles/default

adjusting 'compiler.libcxx=libstdc++11'
"""
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


def detected_os():
    result = platform.system()
    if result == "Darwin":
        return "Macos"
    if result.startswith("CYGWIN"):
        return "Windows"
    return result


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
    arch = architectures.get(platform.machine().lower(), platform.machine().lower())
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


def detect_defaults_settings(output):
    """ try to deduce current machine values without any constraints at all
    """
    result = []
    _detect_os_arch(result, output)
    _detect_compiler_version(result, output)
    result.append(("build_type", "Release"))

    return result
