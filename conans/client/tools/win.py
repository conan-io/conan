import json
import os
import platform
import re
import deprecation

import subprocess

from contextlib import contextmanager

from conans.client.tools.env import environment_append
from conans.client.tools.oss import detected_architecture, os_info
from conans.errors import ConanException
from conans.util.env_reader import get_env
from conans.util.files import decode_text, save, mkdir_tmp
from conans.unicode import get_cwd
from conans.model.version import Version

_global_output = None


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


def _system_registry_key(key, subkey, query):
    from six.moves import winreg  # @UnresolvedImport
    try:
        hkey = winreg.OpenKey(key, subkey)
    except (OSError, WindowsError):  # Raised by OpenKey/Ex if the function fails (py3, py2)
        return None
    else:
        try:
            value, _ = winreg.QueryValueEx(hkey, query)
            return value
        except EnvironmentError:
            return None
        finally:
            winreg.CloseKey(hkey)


def _visual_compiler(output, version):
    """"version have to be 8.0, or 9.0 or... anything .0"""
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
    is_64bits = _system_registry_key(winreg.HKEY_LOCAL_MACHINE,
                                     r"SOFTWARE\Microsoft\Windows\CurrentVersion",
                                     "ProgramFilesDir (x86)") is not None

    if is_64bits:
        key_name = r'SOFTWARE\Wow6432Node\Microsoft\VisualStudio\SxS\VC7'
    else:
        key_name = r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\VisualStudio\SxS\VC7'

    if _system_registry_key(winreg.HKEY_LOCAL_MACHINE, key_name, version):
        installed_version = Version(version).major(fill=False)
        compiler = "Visual Studio"
        output.success("Found %s %s" % (compiler, installed_version))
        return compiler, installed_version

    return None


def latest_vs_version_installed():
    return latest_visual_studio_version_installed(_global_output)


def latest_visual_studio_version_installed(output):
    for version in reversed(["8", "9", "10", "11", "12", "14", "15"]):
        vs = _visual_compiler(output, version)
        if vs:
            return vs[1]
    return None


@deprecation.deprecated(deprecated_in="1.2", removed_in="2.0",
                        details="Use the MSBuild() build helper instead")
def msvc_build_command(settings, sln_path, targets=None, upgrade_project=True, build_type=None,
                       arch=None, parallel=True, force_vcvars=False, toolset=None, platforms=None):
    """ Do both: set the environment variables and call the .sln build
    """
    import warnings
    warnings.warn("deprecated", DeprecationWarning)

    vcvars = vcvars_command(settings, force=force_vcvars)
    build = build_sln_command(settings, sln_path, targets, upgrade_project, build_type, arch,
                              parallel, toolset=toolset, platforms=platforms)
    command = "%s && %s" % (vcvars, build)
    return command


@deprecation.deprecated(deprecated_in="1.2", removed_in="2.0",
                        details="Use the MSBuild() build helper instead")
def build_sln_command(settings, sln_path, targets=None, upgrade_project=True, build_type=None,
                      arch=None, parallel=True, toolset=None, platforms=None):
    """
    Use example:
        build_command = build_sln_command(self.settings, "myfile.sln", targets=["SDL2_image"])
        command = "%s && %s" % (tools.vcvars_command(self.settings), build_command)
        self.run(command)
    """
    from conans.client.build.msbuild import MSBuild
    tmp = MSBuild(settings)
    tmp._output = _global_output

    # Generate the properties file
    props_file_contents = tmp._get_props_file_contents()
    tmp_path = os.path.join(mkdir_tmp(), ".conan_properties")
    save(tmp_path, props_file_contents)

    # Build command
    command = tmp.get_command(sln_path, tmp_path,
                              targets=targets, upgrade_project=upgrade_project,
                              build_type=build_type, arch=arch, parallel=parallel,
                              toolset=toolset, platforms=platforms, use_env=False)

    return command


def vs_installation_path(version, preference=None):

    vs_installation_path = None

    if not preference:
        env_prefs = get_env("CONAN_VS_INSTALLATION_PREFERENCE", list())

        if env_prefs:
            preference = env_prefs
        else:  # default values
            preference = ["Enterprise", "Professional", "Community", "BuildTools"]

    # Try with vswhere()
    try:
        legacy_products = vswhere(legacy=True)
        all_products = vswhere(products=["*"])
        products = legacy_products + all_products
    except ConanException:
        products = None

    vs_paths = []

    if products:
        # remove repeated products
        seen_products = []
        for product in products:
            if product not in seen_products:
                seen_products.append(product)

        # Append products with "productId" by order of preference
        for product_type in preference:
            for product in seen_products:
                product = dict(product)
                if product["installationVersion"].startswith(("%d." % int(version))) and "productId" in product:
                    if product_type in product["productId"]:
                        vs_paths.append(product["installationPath"])

        # Append products without "productId" (Legacy installations)
        for product in seen_products:
            product = dict(product)
            if product["installationVersion"].startswith(("%d." % int(version))) and "productId" not in product:
                vs_paths.append(product["installationPath"])

    # If vswhere does not find anything or not available, try with vs_comntools()
    if not vs_paths:
        vs_path = vs_comntools(version)

        if vs_path:
            sub_path_to_remove = os.path.join("", "Common7", "Tools", "")
            # Remove '\\Common7\\Tools\\' to get same output as vswhere
            if vs_path.endswith(sub_path_to_remove):
                vs_path = vs_path[:-(len(sub_path_to_remove)+1)]

        vs_installation_path = vs_path
    else:
        vs_installation_path = vs_paths[0]

    return vs_installation_path


def vswhere(all_=False, prerelease=False, products=None, requires=None, version="", latest=False,
            legacy=False, property_="", nologo=True):

    # 'version' option only works if Visual Studio 2017 is installed:
    # https://github.com/Microsoft/vswhere/issues/91

    products = list() if products is None else products
    requires = list() if requires is None else requires

    if legacy and (products or requires):
        raise ConanException("The 'legacy' parameter cannot be specified with either the "
                             "'products' or 'requires' parameter")

    program_files = os.environ.get("ProgramFiles(x86)", os.environ.get("ProgramFiles"))

    if program_files:
        vswhere_path = os.path.join(program_files, "Microsoft Visual Studio", "Installer",
                                    "vswhere.exe")
        if not os.path.isfile(vswhere_path):
            raise ConanException("Cannot locate 'vswhere'")
    else:
        raise ConanException("Cannot locate 'Program Files'/'Program Files (x86)' directory")

    arguments = list()
    arguments.append(vswhere_path)

    # Output json format
    arguments.append("-format")
    arguments.append("json")

    if all_:
        arguments.append("-all")

    if prerelease:
        arguments.append("-prerelease")

    if products:
        arguments.append("-products")
        arguments.extend(products)

    if requires:
        arguments.append("-requires")
        arguments.extend(requires)

    if len(version) is not 0:
        arguments.append("-version")
        arguments.append(version)

    if latest:
        arguments.append("-latest")

    if legacy:
        arguments.append("-legacy")

    if len(property_) is not 0:
        arguments.append("-property")
        arguments.append(property_)

    if nologo:
        arguments.append("-nologo")

    try:
        output = subprocess.check_output(arguments)
        output = decode_text(output).strip()
        # Ignore the "description" field, that even decoded contains non valid charsets for json
        # (ignored ones)
        output = "\n".join([line for line in output.splitlines()
                            if not line.strip().startswith('"description"')])

    except (ValueError, subprocess.CalledProcessError, UnicodeDecodeError) as e:
        raise ConanException("vswhere error: %s" % str(e))

    return json.loads(output)


def vs_comntools(compiler_version):
    env_var = "vs%s0comntools" % compiler_version
    vs_path = os.getenv(env_var)
    return vs_path


def find_windows_10_sdk():
    """finds valid Windows 10 SDK version which can be passed to vcvarsall.bat (vcvars_command)"""
    # uses the same method as VCVarsQueryRegistry.bat
    from six.moves import winreg  # @UnresolvedImport
    hives = [
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Wow6432Node'),
        (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Wow6432Node'),
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE'),
        (winreg.HKEY_CURRENT_USER, r'SOFTWARE')
    ]
    for key, subkey in hives:
        installation_folder = _system_registry_key(key, r'%s\Microsoft\Microsoft SDKs\Windows\v10.0' % subkey,
                                                   'InstallationFolder')
        if installation_folder:
            if os.path.isdir(installation_folder):
                include_dir = os.path.join(installation_folder, 'include')
                for sdk_version in os.listdir(include_dir):
                    if os.path.isdir(os.path.join(include_dir, sdk_version)) and sdk_version.startswith('10.'):
                        windows_h = os.path.join(include_dir, sdk_version, 'um', 'Windows.h')
                        if os.path.isfile(windows_h):
                            return sdk_version
    return None


def vcvars_command(settings, arch=None, compiler_version=None, force=False, vcvars_ver=None,
                   winsdk_version=None):
    arch_setting = arch or settings.get_safe("arch")

    compiler = settings.get_safe("compiler")
    if compiler == 'Visual Studio':
        compiler_version = compiler_version or settings.get_safe("compiler.version")
    else:
        # vcvars might be still needed for other compilers, e.g. clang-cl or Intel C++,
        # as they might be using Microsoft STL and other tools (e.g. resource compiler, manifest tool, etc)
        # in this case, use the latest Visual Studio available on the machine
        last_version = latest_vs_version_installed()

        compiler_version = compiler_version or last_version
    os_setting = settings.get_safe("os")
    if not compiler_version:
        raise ConanException("compiler.version setting required for vcvars not defined")

    # https://msdn.microsoft.com/en-us/library/f2ccy3wt.aspx
    arch_setting = arch_setting or 'x86_64'
    arch_build = settings.get_safe("arch_build") or detected_architecture()
    if arch_build == 'x86_64':
        vcvars_arch = {'x86': 'amd64_x86' if int(compiler_version) >= 12 else 'x86',
                       'x86_64': 'amd64',
                       'armv7': 'amd64_arm',
                       'armv8': 'amd64_arm64'}.get(arch_setting)
    elif arch_build == 'x86':
        vcvars_arch = {'x86': 'x86',
                       'x86_64': 'x86_amd64',
                       'armv7': 'x86_arm',
                       'armv8': 'x86_arm64'}.get(arch_setting)
    if not vcvars_arch:
        raise ConanException('unsupported architecture %s' % arch_setting)

    existing_version = os.environ.get("VisualStudioVersion")

    if existing_version:
        command = ["echo Conan:vcvars already set"]
        existing_version = existing_version.split(".")[0]
        if existing_version != compiler_version:
            message = "Visual environment already set to %s\n " \
                      "Current settings visual version: %s" % (existing_version, compiler_version)
            if not force:
                raise ConanException("Error, %s" % message)
            else:
                _global_output.warn(message)
    else:
        vs_path = vs_installation_path(str(compiler_version))

        if not vs_path or not os.path.isdir(vs_path):
            raise ConanException("VS non-existing installation: Visual Studio %s" % str(compiler_version))
        else:
            if int(compiler_version) > 14:
                vcvars_path = os.path.join(vs_path, "VC/Auxiliary/Build/vcvarsall.bat")
                command = ['set "VSCMD_START_DIR=%%CD%%" && '
                           'call "%s" %s' % (vcvars_path, vcvars_arch)]
            else:
                vcvars_path = os.path.join(vs_path, "VC/vcvarsall.bat")
                command = ['call "%s" %s' % (vcvars_path, vcvars_arch)]
        if int(compiler_version) >= 14:
            if winsdk_version:
                command.append(winsdk_version)
            if vcvars_ver:
                command.append("-vcvars_ver=%s" % vcvars_ver)

    if os_setting == 'WindowsStore':
        os_version_setting = settings.get_safe("os.version")
        if os_version_setting == '8.1':
            command.append('store 8.1')
        elif os_version_setting == '10.0':
            windows_10_sdk = find_windows_10_sdk()
            if not windows_10_sdk:
                raise ConanException("cross-compiling for WindowsStore 10 (UWP), "
                                     "but Windows 10 SDK wasn't found")
            command.append('store %s' % windows_10_sdk)
        else:
            raise ConanException('unsupported Windows Store version %s' % os_version_setting)
    return " ".join(command)


def vcvars_dict(settings, arch=None, compiler_version=None, force=False, filter_known_paths=False,
                vcvars_ver=None, winsdk_version=None, only_diff=True):
    known_path_lists = ("include", "lib", "libpath", "path")
    cmd = vcvars_command(settings, arch=arch,
                         compiler_version=compiler_version, force=force,
                         vcvars_ver=vcvars_ver, winsdk_version=winsdk_version) + " && echo __BEGINS__ && set"
    ret = decode_text(subprocess.check_output(cmd, shell=True))
    new_env = {}
    start_reached = False
    for line in ret.splitlines():
        line = line.strip()
        if not start_reached:
            if "__BEGINS__" in line:
                start_reached = True
            continue

        if line == "\n" or not line:
            continue
        try:
            name_var, value = line.split("=", 1)
            new_value = value.split(os.pathsep) if name_var.lower() in known_path_lists else value
            # Return only new vars & changed ones, but only with the changed elements if the var is
            # a list
            if only_diff:
                old_value = os.environ.get(name_var)
                if name_var.lower() == "path":
                    old_values_lower = [v.lower() for v in old_value.split(os.pathsep)]
                    # Clean all repeated entries, not append if the element was already there
                    new_env[name_var] = [v for v in new_value if v.lower() not in old_values_lower]
                elif old_value and value.endswith(os.pathsep + old_value):
                    # The new value ends with separator and the old value, is a list, get only the new elements
                    new_env[name_var] = value[:-(len(old_value) + 1)].split(os.pathsep)
                elif value != old_value:
                    # Only if the vcvars changed something, we return the variable,
                    # otherwise is not vcvars related
                    new_env[name_var] = new_value
            else:
                new_env[name_var] = new_value

        except ValueError:
            pass

    if filter_known_paths:
        def relevant_path(path):
            path = path.replace("\\", "/").lower()
            keywords = "msbuild", "visual", "microsoft", "/msvc/", "/vc/", "system32", "windows"
            return any(word in path for word in keywords)

        path = new_env.get("PATH", "").split(";")
        path = [entry for entry in path if relevant_path(entry)]
        new_env["PATH"] = ";".join(path)

    return new_env

@contextmanager
def vcvars(*args, **kwargs):
    if platform.system() == "Windows":
        new_env = vcvars_dict(*args, **kwargs)
        with environment_append(new_env):
            yield
    else:
        yield


def escape_windows_cmd(command):
    """ To use in a regular windows cmd.exe
        1. Adds escapes so the argument can be unpacked by CommandLineToArgvW()
        2. Adds escapes for cmd.exe so the argument survives cmd.exe's substitutions.

        Useful to escape commands to be executed in a windows bash (msys2, cygwin etc)
    """
    quoted_arg = subprocess.list2cmdline([command])
    return "".join(["^%s" % arg if arg in r'()%!^"<>&|' else arg for arg in quoted_arg])


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


MSYS2 = 'msys2'
MSYS = 'msys'
CYGWIN = 'cygwin'
WSL = 'wsl'  # Windows Subsystem for Linux
SFU = 'sfu'  # Windows Services for UNIX


def unix_path(path, path_flavor=None):
    """"Used to translate windows paths to MSYS unix paths like
    c/users/path/to/file. Not working in a regular console or MinGW!"""
    if not path:
        return None

    if os.path.exists(path):
        path = get_cased_path(path)  # if the path doesn't exist (and abs) we cannot guess the casing

    path_flavor = path_flavor or os_info.detect_windows_subsystem() or MSYS2
    path = path.replace(":/", ":\\")
    pattern = re.compile(r'([a-z]):\\', re.IGNORECASE)
    path = pattern.sub('/\\1/', path).replace('\\', '/')
    if path_flavor in (MSYS, MSYS2):
        return path.lower()
    elif path_flavor == CYGWIN:
        return '/cygdrive' + path.lower()
    elif path_flavor == WSL:
        return '/mnt' + path[0:2].lower() + path[2:]
    elif path_flavor == SFU:
        path = path.lower()
        return '/dev/fs' + path[0] + path[1:].capitalize()
    return None


def run_in_windows_bash(conanfile, bashcmd, cwd=None, subsystem=None, msys_mingw=True, env=None):
    """ Will run a unix command inside a bash terminal
        It requires to have MSYS2, CYGWIN, or WSL
    """
    env = env or {}
    if platform.system() != "Windows":
        raise ConanException("Command only for Windows operating system")
    subsystem = subsystem or os_info.detect_windows_subsystem()

    if not subsystem:
        raise ConanException("Cannot recognize the Windows subsystem, install MSYS2/cygwin or specify a build_require "
                             "to apply it.")

    if subsystem == MSYS2 and msys_mingw:
        # This needs to be set so that msys2 bash profile will set up the environment correctly.
        env_vars = {"MSYSTEM": "MINGW32" if conanfile.settings.get_safe("arch") == "x86" else "MINGW64",
                    "MSYS2_PATH_TYPE": "inherit"}
    else:
        env_vars = {}

    with environment_append(env_vars):
        hack_env = ""
        if subsystem != WSL:  # In the bash.exe from WSL this trick do not work, always the /usr/bin etc at first place
            inherited_path = conanfile.env.get("PATH", None)
            if isinstance(inherited_path, list):
                paths = [unix_path(path, path_flavor=subsystem) for path in inherited_path]
                inherited_path = ":".join(paths)
            else:
                inherited_path = unix_path(inherited_path, path_flavor=subsystem)

            if "PATH" in env:
                tmp = unix_path(env["PATH"].replace(";", ":"), path_flavor=subsystem)
                inherited_path = "%s:%s" % (tmp, inherited_path) if inherited_path else tmp

            # Put the build_requires and requires path at the first place inside the shell
            hack_env = ' && PATH="%s:$PATH"' % inherited_path if inherited_path else ""

        for var_name, value in env.items():
            if var_name == "PATH":
                continue
            hack_env += ' && %s=%s' % (var_name, value)

        # Needed to change to that dir inside the bash shell
        if cwd and not os.path.isabs(cwd):
            cwd = os.path.join(get_cwd(), cwd)

        curdir = unix_path(cwd or get_cwd(), path_flavor=subsystem)
        to_run = 'cd "%s"%s && %s ' % (curdir, hack_env, bashcmd)
        bash_path = os_info.bash_path()
        bash_path = '"%s"' % bash_path if " " in bash_path else bash_path
        wincmd = '%s --login -c %s' % (bash_path, escape_windows_cmd(to_run))
        conanfile.output.info('run_in_windows_bash: %s' % wincmd)
        # https://github.com/conan-io/conan/issues/2839 (subprocess=True)
        return conanfile._conan_runner(wincmd, output=conanfile.output, subprocess=True)
