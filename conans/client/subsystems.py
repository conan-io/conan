"""
Potential scenarios:

- Running from a Windows native "cmd"
  - Targeting Windows native (os.subsystem = None)
    - No need of bash (no conf at all)
    - Need to build in bash (tools.microsoft.bash:subsystem=xxx,
                             tools.microsoft.bash:path=<path>,
                             conanfile.win_bash)
    - Need to run (tests) in bash (tools.microsoft.bash:subsystem=xxx,
                                   tools.microsoft.bash:path=<path>,
                                   conanfile.win_bash_run)
  - Targeting Subsystem (os.subsystem = msys2/cygwin)
    - Always builds and runs in bash (tools.microsoft.bash:path)

- Running from a subsytem terminal (tools.microsoft.bash:subsystem=xxx,
                                    tools.microsoft.bash:path=None) NO ERROR mode for not specifying it? =CURRENT?
  - Targeting Windows native (os.subsystem = None)
  - Targeting Subsystem (os.subsystem = msys2/cygwin)

"""
import os
import platform
import re
import subprocess

from conans.errors import ConanException

WINDOWS = "windows"
MSYS2 = 'msys2'
MSYS = 'msys'
CYGWIN = 'cygwin'
WSL = 'wsl'  # Windows Subsystem for Linux
SFU = 'sfu'  # Windows Services for UNIX


def command_env_wrapper(conanfile, command, envfiles, envfiles_folder):
    from conan.tools.env.environment import environment_wrap_command
    if platform.system() == "Windows" and conanfile.win_bash:  # New, Conan 2.0
        wrapped_cmd = _windows_bash_wrapper(conanfile, command, envfiles, envfiles_folder)
    else:
        wrapped_cmd = environment_wrap_command(envfiles, envfiles_folder, command)
    return wrapped_cmd


def _windows_bash_wrapper(conanfile, command, env, envfiles_folder):
    from conan.tools.env import Environment
    from conan.tools.env.environment import environment_wrap_command
    """ Will wrap a unix command inside a bash terminal It requires to have MSYS2, CYGWIN, or WSL"""

    subsystem = conanfile.conf.get("tools.microsoft.bash:subsystem")
    shell_path = conanfile.conf.get("tools.microsoft.bash:path")
    if not subsystem or not shell_path:
        raise ConanException("The config 'tools.microsoft.bash:subsystem' and "
                             "'tools.microsoft.bash:path' are "
                             "needed to run commands in a Windows subsystem")
    env = env or []
    if subsystem == MSYS2:
        # Configure MSYS2 to inherith the PATH
        msys2_mode_env = Environment()
        _msystem = {"x86": "MINGW32"}.get(conanfile.settings.get_safe("arch"), "MINGW64")
        msys2_mode_env.define("MSYSTEM", _msystem)
        msys2_mode_env.define("MSYS2_PATH_TYPE", "inherit")
        path = os.path.join(conanfile.generators_folder, "msys2_mode.bat")
        msys2_mode_env.vars(conanfile, "build").save_bat(path)
        env.append(path)

    wrapped_shell = '"%s"' % shell_path if " " in shell_path else shell_path
    wrapped_shell = environment_wrap_command(env, envfiles_folder, wrapped_shell,
                                             accepted_extensions=("bat", "ps1"))

    # Wrapping the inside_command enable to prioritize our environment, otherwise /usr/bin go
    # first and there could be commands that we want to skip
    wrapped_user_cmd = environment_wrap_command(env, envfiles_folder, command,
                                                accepted_extensions=("sh", ))
    wrapped_user_cmd = _escape_windows_cmd(wrapped_user_cmd)

    final_command = '{} -c {}'.format(wrapped_shell, wrapped_user_cmd)
    return final_command


def _escape_windows_cmd(command):
    """ To use in a regular windows cmd.exe
        1. Adds escapes so the argument can be unpacked by CommandLineToArgvW()
        2. Adds escapes for cmd.exe so the argument survives cmd.exe's substitutions.

        Useful to escape commands to be executed in a windows bash (msys2, cygwin etc)
    """
    quoted_arg = subprocess.list2cmdline([command])
    return "".join(["^%s" % arg if arg in r'()%!^"<>&|' else arg for arg in quoted_arg])


def deduce_subsystem(conanfile, scope):
    """ used by:
    - EnvVars: to decide if using :  ; as path separator, translate paths to subsystem
               and decide to generate a .bat or .sh
    - Autotools: to define the full abs path to the "configure" script
    - GnuDeps: to map all the paths from dependencies
    - Aggregation of envfiles: to map each aggregated path to the subsystem
    - unix_path: util for recipes
    """
    if scope.startswith("build"):
        if hasattr(conanfile, "settings_build"):
            the_os = conanfile.settings_build.get_safe("os")
            subsystem = conanfile.settings_build.get_safe("os.subsystem")
        else:
            the_os = platform.system()  # FIXME: Temporary fallback until 2.0
            subsystem = None
    else:
        the_os = conanfile.settings.get_safe("os")
        subsystem = conanfile.settings.get_safe("os.subsystem")

    if not str(the_os).startswith("Windows"):
        return None

    if subsystem is None and not scope.startswith("build"):  # "run" scope do not follow win_bash
        return WINDOWS

    if subsystem is None:  # Not defined by settings, so native windows
        if not conanfile.win_bash:
            return WINDOWS

        subsystem = conanfile.conf.get("tools.microsoft.bash:subsystem")
        if not subsystem:
            raise ConanException("The config 'tools.microsoft.bash:subsystem' is "
                                 "needed to run commands in a Windows subsystem")
    return subsystem


def subsystem_path(subsystem, path):
    """"Used to translate windows paths to MSYS unix paths like
    c/users/path/to/file. Not working in a regular console or MinGW!
    """
    if subsystem is None or subsystem == WINDOWS:
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
