import re
from subprocess import Popen, PIPE, STDOUT
import platform
from conans.client.output import Color
from conans.model.version import Version
import os


def execute(command):
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


def gcc_compiler(output):
    try:
        _, out = execute('gcc -dumpversion')
        compiler = "gcc"
        installed_version = Version(out).minor(fill=False)
        if installed_version:
            output.success("Found %s %s" % (compiler, installed_version))
            return compiler, installed_version
    except:
        pass


def clang_compiler(output):
    try:
        _, out = execute('clang --version')
        if "Apple" in out:
            compiler = "apple-clang"
        elif "clang version" in out:
            compiler = "clang"
        installed_version = re.search("([0-9]\.[0-9])", out).group()
        output.success("Found %s %s" % (compiler, installed_version))
        return compiler, Version(installed_version)
    except:
        pass


def visual_compiler_version(version):
    'version have to be 8.0, or 9.0 or... anything .0'
    import _winreg

    try:
        hKey = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\Microsoft\Windows\CurrentVersion")
        _winreg.QueryValueEx(hKey, "ProgramFilesDir (x86)")
        is_64bits = True
    except EnvironmentError:
        is_64bits = False
    finally:
        _winreg.CloseKey(hKey)

    if is_64bits:
        key_name = r'SOFTWARE\Wow6432Node\Microsoft\VisualStudio\SxS\VC7'
    else:
        key_name = r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\VisualStudio\SxS\VC7'

    try:
        key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, key_name)
        _winreg.QueryValueEx(key, version)
        return Version(version).major(fill=False)
    except EnvironmentError:
        pass


def visual_compiler(output):
    compiler = "Visual Studio"
    last_version = None
    for version in ["8.0", "9.0", "10.0", "11.0", "12.0", "14.0"]:
        vs = visual_compiler_version(version)
        if vs:
            compiler = "Visual Studio"
            last_version = vs
            output.success("Found %s %s" % (compiler, last_version))
    if last_version:
        return compiler, last_version


def get_default_compiler(output):
    if platform.system() == "Windows":
        vs = visual_compiler(output)

    gcc = gcc_compiler(output)
    clang = clang_compiler(output)
    env_priorized = priorize_by_env(gcc, clang, output)
    if env_priorized:
        return env_priorized

    if platform.system() == "Windows":
        return vs or gcc or clang
    elif platform.system() == "Darwin":
        return clang or gcc
    else:
        return gcc or clang


def priorize_by_env(gcc, clang, output):

    cc = os.environ.get("CC", "")
    cxx = os.environ.get("CXX", "")
    output.info("CC and CXX: %s, %s " % (cc, cxx))
    if "clang" == cc or "clang++" == cxx:
        output.info("Detected clang compiler in env CC/CXX")
        return clang
    if "gcc" == cc or "g++" == cxx:
        output.info("Detected gcc compiler in env CC/CXX")
        return gcc
    else:
        return None



def detect_defaults_settings(output):
    """ try to deduce current machine values without any
    constraints at all
    """
    output.writeln("\nIt seems to be the first time you run conan",
                   Color.BRIGHT_YELLOW)
    output.writeln("Auto detecting your dev setup to initialize conan.conf",
                   Color.BRIGHT_YELLOW)
    result = []
    architectures = {'i386': 'x86',
                     'amd64': 'x86_64'}

    systems = {'Darwin': 'Macos'}
    result.append(("os", systems.get(platform.system(), platform.system())))
    arch = architectures.get(platform.machine().lower(), platform.machine().lower())
    arch = 'arm' if arch.startswith('arm') else arch
    result.append(("arch", arch))

    try:
        compiler, version = get_default_compiler(output)
    except:
        compiler, version = None, None
    if not compiler or not version:
        output.error("Unable to find a working compiler")
    else:
        result.append(("compiler", compiler))
        result.append(("compiler.version", version))
        if compiler == "Visual Studio":
            result.append(("compiler.runtime", "MD"))

    result.append(("build_type", "Release"))
    output.writeln("Default conan.conf settings", Color.BRIGHT_YELLOW)
    output.writeln("\n".join(["\t%s=%s" % (k, v) for (k, v) in result]), Color.BRIGHT_YELLOW)
    output.writeln("*** You can change them in ~/.conan/conan.conf ***", Color.BRIGHT_MAGENTA)
    output.writeln("*** Or override with -s compiler='other' -s ...s***\n\n", Color.BRIGHT_MAGENTA)
    return result
