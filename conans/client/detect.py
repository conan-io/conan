import re
from subprocess import Popen, PIPE, STDOUT
import platform
from conans.client.output import Color
from conans.model.version import Version
import os


def _execute(command):
    proc = Popen(command, shell=True, bufsize=1, stdout=PIPE, stderr=STDOUT)

    output_buffer = []
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        # output.write(line)
        output_buffer.append(line)

    proc.communicate()
    return proc.returncode, "".join(output_buffer)


def _gcc_compiler(output, compiler_exe="gcc"):
    try:
        _, out = _execute('%s -dumpversion' % compiler_exe)
        compiler = "gcc"
        installed_version = re.search("([0-9]\.[0-9])", out).group()
        if installed_version:
            output.success("Found %s %s" % (compiler, installed_version))
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


def _visual_compiler(output, version):
    'version have to be 8.0, or 9.0 or... anything .0'
    from six.moves import winreg

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
    for version in ["8.0", "9.0", "10.0", "11.0", "12.0", "14.0"]:
        vs = _visual_compiler(output, version)
        last_version = vs or last_version
    return last_version


def _get_default_compiler(output):
    cc = os.environ.get("CC", "")
    cxx = os.environ.get("CXX", "")
    if cc or cxx:  # Env defined, use them
        output.info("CC and CXX: %s, %s " % (cc or "None", cxx or "None"))
        command = cc or cxx
        if "gcc" in command:
            return _gcc_compiler(output, command)
        if "clang" in command.lower():
            return _clang_compiler(output, command)
        # I am not able to find its version
        output.error("Not able to automatically detect '%s' version" % command)
        return None

    if platform.system() == "Windows":
        vs = _visual_compiler_last(output)
    gcc = _gcc_compiler(output)
    clang = _clang_compiler(output)

    if platform.system() == "Windows":
        return vs or gcc or clang
    elif platform.system() == "Darwin":
        return clang or gcc
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
        if compiler == "Visual Studio":
            result.append(("compiler.runtime", "MD"))
        elif compiler == "apple-clang":
            result.append(("compiler.libcxx", "libc++"))
        elif compiler == "gcc" or "clang" in compiler:
            result.append(("compiler.libcxx", "libstdc++"))


def _detect_os_arch(result, output):
    architectures = {'i386': 'x86',
                     'amd64': 'x86_64'}

    systems = {'Darwin': 'Macos'}
    result.append(("os", systems.get(platform.system(), platform.system())))
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


def detect_defaults_settings(output):
    """ try to deduce current machine values without any
    constraints at all
    """
    output.writeln("\nIt seems to be the first time you run conan", Color.BRIGHT_YELLOW)
    output.writeln("Auto detecting your dev setup to initialize conan.conf", Color.BRIGHT_YELLOW)

    result = []
    _detect_os_arch(result, output)
    _detect_compiler_version(result, output)
    result.append(("build_type", "Release"))

    output.writeln("Default conan.conf settings", Color.BRIGHT_YELLOW)
    output.writeln("\n".join(["\t%s=%s" % (k, v) for (k, v) in result]), Color.BRIGHT_YELLOW)
    output.writeln("*** You can change them in ~/.conan/conan.conf ***", Color.BRIGHT_MAGENTA)
    output.writeln("*** Or override with -s compiler='other' -s ...s***\n\n", Color.BRIGHT_MAGENTA)
    return result
