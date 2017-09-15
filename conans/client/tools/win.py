import os
import platform

import subprocess

from conans.client.tools.env import environment_append
from conans.client.tools.files import unix_path
from conans.errors import ConanException

_global_output = None


def msvc_build_command(settings, sln_path, targets=None, upgrade_project=True, build_type=None,
                       arch=None):
    """ Do both: set the environment variables and call the .sln build
    """
    vcvars = vcvars_command(settings)
    build = build_sln_command(settings, sln_path, targets, upgrade_project, build_type, arch)
    command = "%s && %s" % (vcvars, build)
    return command


def build_sln_command(settings, sln_path, targets=None, upgrade_project=True, build_type=None,
                      arch=None):
    """
    Use example:
        build_command = build_sln_command(self.settings, "myfile.sln", targets=["SDL2_image"])
        command = "%s && %s" % (tools.vcvars_command(self.settings), build_command)
        self.run(command)
    """
    targets = targets or []
    command = "devenv %s /upgrade && " % sln_path if upgrade_project else ""
    build_type = build_type or settings.build_type
    arch = arch or settings.arch
    if not build_type:
        raise ConanException("Cannot build_sln_command, build_type not defined")
    if not arch:
        raise ConanException("Cannot build_sln_command, arch not defined")
    command += "msbuild %s /p:Configuration=%s" % (sln_path, build_type)
    arch = str(arch)
    if arch in ["x86_64", "x86"]:
        command += ' /p:Platform='
        command += '"x64"' if arch == "x86_64" else '"x86"'
    elif "ARM" in arch.upper():
        command += ' /p:Platform="ARM"'

    if targets:
        command += " /target:%s" % ";".join(targets)
    return command


def vs_installation_path(version):
    if not hasattr(vs_installation_path, "_cached"):
        vs_installation_path._cached = dict()

    if version not in vs_installation_path._cached:
        vs_path = None
        program_files = os.environ.get("ProgramFiles(x86)", os.environ.get("ProgramFiles"))
        if program_files:
            vswhere_path = os.path.join(program_files, "Microsoft Visual Studio", "Installer",
                                        "vswhere.exe")
            if os.path.isfile(vswhere_path):
                version_range = "[%d.0, %d.0)" % (int(version), int(version) + 1)
                try:
                    output = subprocess.check_output([vswhere_path, "-version", version_range,
                                                      "-legacy", "-property", "installationPath"])
                    vs_path = output.decode().strip()
                    _global_output.info("vswhere detected VS %s in %s" % (version, vs_path))
                except (ValueError, subprocess.CalledProcessError, UnicodeDecodeError) as e:
                    _global_output.error("vswhere error: %s" % str(e))

        # Remember to cache result
        vs_installation_path._cached[version] = vs_path

    return vs_installation_path._cached[version]


def vcvars_command(settings):
    arch_setting = settings.get_safe("arch")
    compiler_version = settings.get_safe("compiler.version")
    if not compiler_version:
        raise ConanException("compiler.version setting required for vcvars not defined")

    param = "x86" if arch_setting == "x86" else "amd64"
    existing_version = os.environ.get("VisualStudioVersion")
    if existing_version:
        command = "echo Conan:vcvars already set"
        existing_version = existing_version.split(".")[0]
        if existing_version != compiler_version:
            raise ConanException("Error, Visual environment already set to %s\n"
                                 "Current settings visual version: %s"
                                 % (existing_version, compiler_version))
    else:
        env_var = "vs%s0comntools" % compiler_version

        if env_var == 'vs150comntools':
            vs_path = os.getenv(env_var)
            if not vs_path:  # Try to locate with vswhere
                vs_root = vs_installation_path("15")
                if vs_root:
                    vs_path = os.path.join(vs_root, "Common7", "Tools")
                else:
                    raise ConanException("VS2017 '%s' variable not defined, "
                                         "and vswhere didn't find it" % env_var)
            vcvars_path = os.path.join(vs_path, "../../VC/Auxiliary/Build/vcvarsall.bat")
            command = ('set "VSCMD_START_DIR=%%CD%%" && '
                       'call "%s" %s' % (vcvars_path, param))
        else:
            try:
                vs_path = os.environ[env_var]
            except KeyError:
                raise ConanException("VS '%s' variable not defined. Please install VS" % env_var)
            vcvars_path = os.path.join(vs_path, "../../VC/vcvarsall.bat")
            command = ('call "%s" %s' % (vcvars_path, param))

    return command


def escape_windows_cmd(command):
    """ To use in a regular windows cmd.exe
        1. Adds escapes so the argument can be unpacked by CommandLineToArgvW()
        2. Adds escapes for cmd.exe so the argument survives cmd.exe's substitutions.

        Useful to escape commands to be executed in a windows bash (msys2, cygwin etc)
    """
    quoted_arg = subprocess.list2cmdline([command])
    return "".join(["^%s" % arg if arg in r'()%!^"<>&|' else arg for arg in quoted_arg])


def run_in_windows_bash(conanfile, bashcmd, cwd=None):
    """ Will run a unix command inside the msys2 environment
        It requires to have MSYS2 in the path and MinGW
    """
    if platform.system() != "Windows":
        raise ConanException("Command only for Windows operating system")
    # This needs to be set so that msys2 bash profile will set up the environment correctly.
    try:
        arch = conanfile.settings.arch  # Maybe arch doesn't exist
    except:
        arch = None
    env_vars = {"MSYSTEM": "MINGW32" if arch == "x86" else "MINGW64",
                "MSYS2_PATH_TYPE": "inherit"}
    with environment_append(env_vars):
        curdir = unix_path(cwd or os.path.abspath(os.path.curdir))
        # Needed to change to that dir inside the bash shell
        to_run = 'cd "%s" && %s ' % (curdir, bashcmd)
        custom_bash_path = os.getenv("CONAN_BASH_PATH", "bash")
        wincmd = '%s --login -c %s' % (custom_bash_path, escape_windows_cmd(to_run))
        conanfile.output.info('run_in_windows_bash: %s' % wincmd)
        conanfile.run(wincmd)
