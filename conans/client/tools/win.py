import json
import os
import platform
import re
import subprocess
import warnings
from collections import namedtuple
from contextlib import contextmanager

from conans.client.tools import which
from conans.client.tools.env import environment_append
from conans.client.tools.oss import OSInfo, detected_architecture, get_build_os_arch
from conans.errors import ConanException
from conans.model.version import Version
from conans.unicode import get_cwd
from conans.util.conan_v2_mode import conan_v2_behavior
from conans.util.env_reader import get_env
from conans.util.fallbacks import default_output
from conans.util.files import mkdir_tmp, save
from conans.util.runners import check_output_runner


def _visual_compiler_cygwin(output, version):
    if os.path.isfile("/proc/registry/HKEY_LOCAL_MACHINE/SOFTWARE/Microsoft/Windows/"
                      "CurrentVersion/ProgramFilesDir (x86)"):
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


def is_win64():
    from six.moves import winreg  # @UnresolvedImport
    return _system_registry_key(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\Microsoft\Windows\CurrentVersion",
                                "ProgramFilesDir (x86)") is not None


def _visual_compiler(output, version):
    """"version have to be 8.0, or 9.0 or... anything .0"""
    if platform.system().startswith("CYGWIN"):
        return _visual_compiler_cygwin(output, version)

    if Version(version) >= "15":
        vs_path = os.getenv('vs%s0comntools' % version)
        path = vs_path or vs_installation_path(version)
        if path:
            compiler = "Visual Studio"
            output.success("Found %s %s" % (compiler, version))
            return compiler, version
        return None

    version = "%s.0" % version

    from six.moves import winreg  # @UnresolvedImport
    if is_win64():
        key_name = r'SOFTWARE\Wow6432Node\Microsoft\VisualStudio\SxS\VC7'
    else:
        key_name = r'SOFTWARE\Microsoft\VisualStudio\SxS\VC7'

    if _system_registry_key(winreg.HKEY_LOCAL_MACHINE, key_name, version):
        installed_version = Version(version).major(fill=False)
        compiler = "Visual Studio"
        output.success("Found %s %s" % (compiler, installed_version))
        return compiler, installed_version

    return None


def latest_vs_version_installed(output):
    return latest_visual_studio_version_installed(output=output)


MSVS_YEAR = {"16": "2019",
             "15": "2017",
             "14": "2015",
             "12": "2013",
             "11": "2012",
             "10": "2010",
             "9": "2008",
             "8": "2005"}


MSVS_DEFAULT_TOOLSETS = {"16": "v142",
                         "15": "v141",
                         "14": "v140",
                         "12": "v120",
                         "11": "v110",
                         "10": "v100",
                         "9": "v90",
                         "8": "v80"}

# inverse version of the above MSVS_DEFAULT_TOOLSETS (keys and values are swapped)
MSVS_DEFAULT_TOOLSETS_INVERSE = {"v142": "16",
                                 "v141": "15",
                                 "v140": "14",
                                 "v120": "12",
                                 "v110": "11",
                                 "v100": "10",
                                 "v90": "9",
                                 "v80": "8"}


def msvs_toolset(conanfile):
    from conans.model.conan_file import ConanFile

    if isinstance(conanfile, ConanFile):
        settings = conanfile.settings
    else:
        settings = conanfile
    toolset = settings.get_safe("compiler.toolset")
    if not toolset:
        compiler_version = settings.get_safe("compiler.version")
        if settings.get_safe("compiler") == "intel":
            compiler_version = compiler_version if "." in compiler_version else \
                "%s.0" % compiler_version
            toolset = "Intel C++ Compiler " + compiler_version
        else:
            toolset = MSVS_DEFAULT_TOOLSETS.get(compiler_version)
    return toolset


def latest_visual_studio_version_installed(output):
    msvc_sersions = reversed(sorted(list(MSVS_DEFAULT_TOOLSETS.keys()), key=int))
    for version in msvc_sersions:
        vs = _visual_compiler(output, version)
        if vs:
            return vs[1]
    return None


def msvc_build_command(settings, sln_path, targets=None, upgrade_project=True, build_type=None,
                       arch=None, parallel=True, force_vcvars=False, toolset=None, platforms=None,
                       output=None):
    """ Do both: set the environment variables and call the .sln build
    """
    conan_v2_behavior("'tools.msvc_build_command' is deprecated, use 'MSBuild()' helper instead")
    vcvars_cmd = vcvars_command(settings, force=force_vcvars, output=output)
    build = build_sln_command(settings, sln_path, targets, upgrade_project, build_type, arch,
                              parallel, toolset=toolset, platforms=platforms, output=output)
    command = "%s && %s" % (vcvars_cmd, build)
    return command


def build_sln_command(settings, sln_path, targets=None, upgrade_project=True, build_type=None,
                      arch=None, parallel=True, toolset=None, platforms=None, output=None,
                      verbosity=None, definitions=None):
    """
    Use example:
        build_command = build_sln_command(self.settings, "myfile.sln", targets=["SDL2_image"])
        command = "%s && %s" % (tools.vcvars_command(self.settings), build_command)
        self.run(command)
    """
    conan_v2_behavior("'tools.build_sln_command' is deprecated, use 'MSBuild()' helper instead")
    from conans.client.build.msbuild import MSBuildHelper
    tmp = MSBuildHelper(settings)
    output = default_output(output, fn_name='conans.client.tools.win.build_sln_command')
    tmp._output = output

    # Generate the properties file
    props_file_contents = tmp._get_props_file_contents(definitions)
    tmp_path = os.path.join(mkdir_tmp(), ".conan_properties")
    save(tmp_path, props_file_contents)

    # Build command
    command = tmp.get_command(sln_path, tmp_path,
                              targets=targets, upgrade_project=upgrade_project,
                              build_type=build_type, arch=arch, parallel=parallel,
                              toolset=toolset, platforms=platforms, use_env=False,
                              verbosity=verbosity)

    return command


def vs_installation_path(version, preference=None):

    if not preference:
        preference = get_env("CONAN_VS_INSTALLATION_PREFERENCE", list())
        if not preference:  # default values
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
                if (product["installationVersion"].startswith(("%d." % int(version)))
                        and "productId" in product):
                    if product_type in product["productId"]:
                        vs_paths.append(product["installationPath"])

        # Append products without "productId" (Legacy installations)
        for product in seen_products:
            product = dict(product)
            if (product["installationVersion"].startswith(("%d." % int(version)))
                    and "productId" not in product):
                vs_paths.append(product["installationPath"])

    # If vswhere does not find anything or not available, try with vs_comntools()
    if not vs_paths:
        vs_path = vs_comntools(version)

        if vs_path:
            sub_path_to_remove = os.path.join("", "Common7", "Tools", "")
            # Remove '\\Common7\\Tools\\' to get same output as vswhere
            if vs_path.endswith(sub_path_to_remove):
                vs_path = vs_path[:-(len(sub_path_to_remove)+1)]

        result_vs_installation_path = vs_path
    else:
        result_vs_installation_path = vs_paths[0]

    return result_vs_installation_path


def vswhere(all_=False, prerelease=False, products=None, requires=None, version="", latest=False,
            legacy=False, property_="", nologo=True):

    # 'version' option only works if Visual Studio 2017 is installed:
    # https://github.com/Microsoft/vswhere/issues/91

    products = list() if products is None else products
    requires = list() if requires is None else requires

    if legacy and (products or requires):
        raise ConanException("The 'legacy' parameter cannot be specified with either the "
                             "'products' or 'requires' parameter")

    installer_path = None
    program_files = get_env("ProgramFiles(x86)") or get_env("ProgramFiles")
    if program_files:
        expected_path = os.path.join(program_files, "Microsoft Visual Studio", "Installer",
                                     "vswhere.exe")
        if os.path.isfile(expected_path):
            installer_path = expected_path
    vswhere_path = installer_path or which("vswhere")

    if not vswhere_path:
        raise ConanException("Cannot locate vswhere in 'Program Files'/'Program Files (x86)' "
                             "directory nor in PATH")

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

    if len(version) != 0:
        arguments.append("-version")
        arguments.append(version)

    if latest:
        arguments.append("-latest")

    if legacy:
        arguments.append("-legacy")

    if len(property_) != 0:
        arguments.append("-property")
        arguments.append(property_)

    if nologo:
        arguments.append("-nologo")

    try:
        output = check_output_runner(arguments).strip()
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
        subkey = r'%s\Microsoft\Microsoft SDKs\Windows\v10.0' % subkey
        installation_folder = _system_registry_key(key, subkey, 'InstallationFolder')
        if installation_folder and os.path.isdir(installation_folder):
            include_dir = os.path.join(installation_folder, 'include')
            for sdk_version in os.listdir(include_dir):
                if (os.path.isdir(os.path.join(include_dir, sdk_version))
                        and sdk_version.startswith('10.')):
                    windows_h = os.path.join(include_dir, sdk_version, 'um', 'Windows.h')
                    if os.path.isfile(windows_h):
                        return sdk_version
    return None


def vcvars_command(conanfile=None, arch=None, compiler_version=None, force=False, vcvars_ver=None,
                   winsdk_version=None, output=None, settings=None):
    # Handle input arguments (backwards compatibility with 'settings' as first argument)
    # TODO: This can be promoted to a decorator pattern for any function
    if conanfile and settings:
        raise ConanException("Do not set both arguments, 'conanfile' and 'settings',"
                             " to call 'vcvars_command' function")

    from conans.model.conan_file import ConanFile
    if conanfile and not isinstance(conanfile, ConanFile):
        return vcvars_command(settings=conanfile, arch=arch, compiler_version=compiler_version,
                              force=force, vcvars_ver=vcvars_ver, winsdk_version=winsdk_version,
                              output=output)

    if settings:
        warnings.warn("argument 'settings' has been deprecated, use 'conanfile' instead")

    if not conanfile:
        # TODO: If Conan is using 'profile_build' here we don't have any information about it,
        #   we are falling back to the old behavior (which is probably wrong here)
        conanfile = namedtuple('_ConanFile', ['settings'])(settings)
    del settings

    # Here starts the actual implementation for this function
    output = default_output(output, 'conans.client.tools.win.vcvars_command')

    arch_setting = arch or conanfile.settings.get_safe("arch")

    compiler = conanfile.settings.get_safe("compiler")
    compiler_base = conanfile.settings.get_safe("compiler.base")
    if compiler == 'Visual Studio':
        compiler_version = compiler_version or conanfile.settings.get_safe("compiler.version")
    elif compiler_base == "Visual Studio":
        compiler_version = compiler_version or conanfile.settings.get_safe("compiler.base.version")
    else:
        # vcvars might be still needed for other compilers, e.g. clang-cl or Intel C++,
        # as they might be using Microsoft STL and other tools
        # (e.g. resource compiler, manifest tool, etc)
        # in this case, use the latest Visual Studio available on the machine
        last_version = latest_vs_version_installed(output=output)

        compiler_version = compiler_version or last_version
    os_setting = conanfile.settings.get_safe("os")
    if not compiler_version:
        raise ConanException("compiler.version setting required for vcvars not defined")

    # https://msdn.microsoft.com/en-us/library/f2ccy3wt.aspx
    vcvars_arch = None
    arch_setting = arch_setting or 'x86_64'

    _, settings_arch_build = get_build_os_arch(conanfile)
    arch_build = settings_arch_build
    if not hasattr(conanfile, 'settings_build'):
        arch_build = arch_build or detected_architecture()

    if os_setting == 'WindowsCE':
        vcvars_arch = "x86"
    elif arch_build == 'x86_64':
        # Only uses x64 tooling if arch_build explicitly defines it, otherwise
        # Keep the VS default, which is x86 toolset
        # This will probably be changed in conan 2.0
        if ((settings_arch_build or os.getenv("PreferredToolArchitecture") == "x64")
           and int(compiler_version) >= 12):
            x86_cross = "amd64_x86"
        else:
            x86_cross = "x86"
        vcvars_arch = {'x86': x86_cross,
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
                output.warn(message)
    else:
        vs_path = vs_installation_path(str(compiler_version))

        if not vs_path or not os.path.isdir(vs_path):
            raise ConanException("VS non-existing installation: Visual Studio %s"
                                 % str(compiler_version))
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
            os_version_setting = conanfile.settings.get_safe("os.version")
            if os_version_setting == '8.1':
                winsdk_version = winsdk_version or "8.1"
                command.append('store %s' % winsdk_version)
            elif os_version_setting == '10.0':
                winsdk_version = winsdk_version or find_windows_10_sdk()
                if not winsdk_version:
                    raise ConanException("cross-compiling for WindowsStore 10 (UWP), "
                                         "but Windows 10 SDK wasn't found")
                command.append('store %s' % winsdk_version)
            else:
                raise ConanException('unsupported Windows Store version %s' % os_version_setting)
    return " ".join(command)


def vcvars_dict(conanfile=None, arch=None, compiler_version=None, force=False,
                filter_known_paths=False, vcvars_ver=None, winsdk_version=None, only_diff=True,
                output=None, settings=None):
    known_path_lists = ("include", "lib", "libpath", "path")
    cmd = vcvars_command(conanfile, settings=settings, arch=arch,
                         compiler_version=compiler_version, force=force,
                         vcvars_ver=vcvars_ver, winsdk_version=winsdk_version, output=output)
    cmd += " && set"
    ret = check_output_runner(cmd)
    new_env = {}
    for line in ret.splitlines():
        line = line.strip()

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
                    # The new value ends with separator and the old value, is a list,
                    # get only the new elements
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
        def relevant_path(_path):
            _path = _path.replace("\\", "/").lower()
            keywords = "msbuild", "visual", "microsoft", "/msvc/", "/vc/", "system32", "windows"
            return any(word in _path for word in keywords)

        path_key = next((name for name in new_env.keys() if "path" == name.lower()), None)
        if path_key:
            path = [entry for entry in new_env.get(path_key, "") if relevant_path(entry)]
            new_env[path_key] = ";".join(path)

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

    if not OSInfo().is_windows:
        return path

    if os.path.exists(path):
        path = get_cased_path(path)  # if the path doesn't exist (and abs) we cannot guess the casing

    path_flavor = path_flavor or OSInfo.detect_windows_subsystem() or MSYS2
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


def run_in_windows_bash(conanfile, bashcmd, cwd=None, subsystem=None, msys_mingw=True, env=None,
                        with_login=True):
    """ Will run a unix command inside a bash terminal
        It requires to have MSYS2, CYGWIN, or WSL
    """
    env = env or {}
    if platform.system() != "Windows":
        raise ConanException("Command only for Windows operating system")
    subsystem = subsystem or OSInfo.detect_windows_subsystem()

    if not subsystem:
        raise ConanException("Cannot recognize the Windows subsystem, install MSYS2/cygwin "
                             "or specify a build_require to apply it.")

    if subsystem == MSYS2 and msys_mingw:
        # This needs to be set so that msys2 bash profile will set up the environment correctly.
        env_vars = {"MSYSTEM": ("MINGW32" if conanfile.settings.get_safe("arch") == "x86" else
                                "MINGW64"),
                    "MSYS2_PATH_TYPE": "inherit"}
    else:
        env_vars = None

    with environment_append(env_vars):

        hack_env = ""
        # In the bash.exe from WSL this trick do not work, always the /usr/bin etc at first place
        if subsystem != WSL:

            def get_path_value(container, subsystem_name):
                """Gets the path from the container dict and returns a
                string with the path for the subsystem_name"""
                _path_key = next((name for name in container.keys() if "path" == name.lower()), None)
                if _path_key:
                    _path_value = container.get(_path_key)
                    if isinstance(_path_value, list):
                        return ":".join([unix_path(path, path_flavor=subsystem_name)
                                         for path in _path_value])
                    else:
                        return unix_path(_path_value, path_flavor=subsystem_name)

            # First get the PATH from the conanfile.env
            inherited_path = get_path_value(conanfile.env, subsystem)
            # Then get the PATH from the real env
            env_path = get_path_value(env, subsystem)

            # Both together
            full_env = ":".join(v for v in [env_path, inherited_path] if v)
            # Put the build_requires and requires path at the first place inside the shell
            hack_env = ' && PATH="%s:$PATH"' % full_env if full_env else ""

        for var_name, value in env.items():
            if var_name == "PATH":
                continue
            hack_env += ' && %s=%s' % (var_name, value)

        # Needed to change to that dir inside the bash shell
        if cwd and not os.path.isabs(cwd):
            cwd = os.path.join(get_cwd(), cwd)

        curdir = unix_path(cwd or get_cwd(), path_flavor=subsystem)
        to_run = 'cd "%s"%s && %s ' % (curdir, hack_env, bashcmd)
        bash_path = OSInfo.bash_path()
        bash_path = '"%s"' % bash_path if " " in bash_path else bash_path
        login = "--login" if with_login else ""
        wincmd = '%s %s -c %s' % (bash_path, login, escape_windows_cmd(to_run))
        conanfile.output.info('run_in_windows_bash: %s' % wincmd)

        # If is there any other env var that we know it contains paths, convert it to unix_path
        used_special_vars = [var for var in ["AR", "AS", "RANLIB", "LD", "STRIP", "CC", "CXX"]
                             if var in conanfile.env.keys()]
        normalized_env = {p: unix_path(conanfile.env[p], path_flavor=subsystem)
                          for p in used_special_vars}

        # https://github.com/conan-io/conan/issues/2839 (subprocess=True)
        with environment_append(normalized_env):
            return conanfile._conan_runner(wincmd, output=conanfile.output, subprocess=True)
