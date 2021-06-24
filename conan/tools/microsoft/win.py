import os
import platform
import re
import subprocess

from conan.tools.env import Environment
from conan.tools.env.environment import environment_wrap_command
from conans.errors import ConanException

MSYS2 = 'msys2'
MSYS = 'msys'
CYGWIN = 'cygwin'
WSL = 'wsl'  # Windows Subsystem for Linux
SFU = 'sfu'  # Windows Services for UNIX


def unix_path(path, subsystem):
    """"Used to translate windows paths to MSYS unix paths like
    c/users/path/to/file. Not working in a regular console or MinGW!"""
    if not path:
        return None

    if not platform.system == "Windows":
        return path

    if os.path.exists(path):
        # if the path doesn't exist (and abs) we cannot guess the casing
        path = get_cased_path(path)

    if path.startswith('\\\\?\\'):
        path = path[4:]
    path = path.replace(":/", ":\\")
    append_prefix = re.match(r'[a-z]:\\', path, re.IGNORECASE)
    pattern = re.compile(r'([a-z]):\\', re.IGNORECASE)
    path = pattern.sub('/\\1/', path).replace('\\', '/')

    if append_prefix:
        if subsystem in (MSYS, MSYS2):
            return path.lower()
        elif subsystem == CYGWIN:
            return '/cygdrive' + path.lower()
        elif subsystem == WSL:
            return '/mnt' + path[0:2].lower() + path[2:]
        elif subsystem == SFU:
            path = path.lower()
            return '/dev/fs' + path[0] + path[1:].capitalize()
    else:
        return path if subsystem == WSL else path.lower()
    return None


def get_cased_path(name):
    if platform.system() != "Windows":
        return name
    if not os.path.isabs(name):
        name = os.path.abspath(name)

    result = []
    current = name
    while True:
        parent, child = os.path.split(current)
        if parent == current:
            break

        child_cased = child
        if os.path.exists(parent):
            children = os.listdir(parent)
            for c in children:
                if c.upper() == child.upper():
                    child_cased = c
                    break
        result.append(child_cased)
        current = parent
    drive, _ = os.path.splitdrive(current)
    result.append(drive)
    return os.sep.join(reversed(result))


def run_in_windows_shell(conanfile, command, cwd=None, subsystem=None):
    """ Will run a unix command inside a bash terminal
        It requires to have MSYS2, CYGWIN, or WSL
    """
    subsystem = subsystem or conanfile.conf["tools.win.shell:subsystem"]
    if not platform.system() != "Windows":
        raise ConanException("Command only for Windows operating system")

    if not subsystem:
        raise ConanException("Cannot recognize the Windows subsystem, install MSYS2/cygwin "
                             "or specify a build_require to apply it.")

    msys2_mode_env = Environment()
    if subsystem == MSYS2:
        msystem = {"x86": "MINGW32"}.get(conanfile.settings.get_safe("arch"), "MINGW64")
        msys2_mode_env.define("MSYSTEM", msystem)
        # TODO: This is not working when opening the "bash" at "c:\msys64\usr\bin\bash.exe"
        #       Also bash looks very incomplete, without many commom commands
        #       This is working if we consider "c:\msys64\msys2_shell.cmd" the shell
        msys2_mode_env.define("MSYS2_PATH_TYPE", "inherit")
        msys2_mode_env.save_sh("msys2_mode", subsystem=subsystem)
        command = environment_wrap_command("msys2_mode", command, subsystem=subsystem)

    # Needed to change to that dir inside the bash shell
    if cwd and not os.path.isabs(cwd):
        cwd = os.path.join(os.getcwd(), cwd)

    curdir = unix_path(cwd or os.getcwd(), subsystem=subsystem)
    to_run = 'cd "%s" && %s ' % (curdir, command)
    shell_path = conanfile.conf["tools.win.shell:path"]
    shell_path = '"%s"' % shell_path if " " in shell_path else shell_path
    login = "--login"
    if platform.system() == "Windows":
        # cmd.exe shell
        wincmd = '%s %s -c %s' % (shell_path, login, escape_windows_cmd(to_run))
    else:
        wincmd = '%s %s -c %s' % (shell_path, login, to_run)
    conanfile.output.info('run_in_windows_bash: %s' % wincmd)
    # https://github.com/conan-io/conan/issues/2839 (subprocess=True)
    return conanfile._conan_runner(wincmd, output=conanfile.output, subprocess=True)


def escape_windows_cmd(command):
    """ To use in a regular windows cmd.exe
        1. Adds escapes so the argument can be unpacked by CommandLineToArgvW()
        2. Adds escapes for cmd.exe so the argument survives cmd.exe's substitutions.

        Useful to escape commands to be executed in a windows bash (msys2, cygwin etc)
    """
    quoted_arg = subprocess.list2cmdline([command])
    return "".join(["^%s" % arg if arg in r'()%!^"<>&|' else arg for arg in quoted_arg])
