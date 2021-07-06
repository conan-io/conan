import os

from conans.client.tools.win import vs_installation_path
from conans.errors import ConanException


def vs_ide_version(conanfile):
    compiler = conanfile.settings.get_safe("compiler")
    compiler_version = (conanfile.settings.get_safe("compiler.base.version") or
                        conanfile.settings.get_safe("compiler.version"))
    if compiler == "msvc":
        toolset_override = conanfile.conf["tools.microsoft.msbuild:vs_version"]
        if toolset_override:
            visual_version = toolset_override
        else:
            version = compiler_version[:4]  # Remove the latest version number 19.1X if existing
            _visuals = {'19.0': '14',  # TODO: This is common to CMake, refactor
                        '19.1': '15',
                        '19.2': '16'}
            visual_version = _visuals[version]
    else:
        visual_version = compiler_version
    return visual_version


def msvc_runtime_flag(conanfile):
    settings = conanfile.settings
    compiler = settings.get_safe("compiler")
    runtime = settings.get_safe("compiler.runtime")
    if compiler == "Visual Studio":
        return runtime
    if compiler == "msvc":
        runtime_type = settings.get_safe("compiler.runtime_type")
        runtime = "MT" if runtime == "static" else "MD"
        if runtime_type == "Debug":
            runtime = "{}d".format(runtime)
        return runtime


def vcvars_command(version, architecture=None, platform_type=None, winsdk_version=None,
                   vcvars_ver=None, start_dir_cd=True):
    """ conan-agnostic construction of vcvars command
    https://docs.microsoft.com/en-us/cpp/build/building-on-the-command-line
    """
    # TODO: This comes from conans/client/tools/win.py vcvars_command()
    cmd = []
    if start_dir_cd:
        cmd.append('set "VSCMD_START_DIR=%CD%" &&')

    # The "call" is useful in case it is called from another .bat script
    cmd.append('call "%s" ' % vcvars_path(version))
    if architecture:
        cmd.append(architecture)
    if platform_type:
        cmd.append(platform_type)
    if winsdk_version:
        cmd.append(winsdk_version)
    if vcvars_ver:
        cmd.append("-vcvars_ver=%s" % vcvars_ver)
    return " ".join(cmd)


def vcvars_path(version):
    # TODO: This comes from conans/client/tools/win.py vcvars_command()
    vs_path = vs_installation_path(version)
    if not vs_path or not os.path.isdir(vs_path):
        raise ConanException("VS non-existing installation: Visual Studio %s" % version)

    if int(version) > 14:
        vcpath = os.path.join(vs_path, "VC/Auxiliary/Build/vcvarsall.bat")
    else:
        vcpath = os.path.join(vs_path, "VC/vcvarsall.bat")
    return vcpath


def vcvars_arch(conanfile):
    """
    computes the vcvars command line architecture based on conanfile settings (host) and
    settings_build
    :param conanfile:
    :return:
    """
    settings_host = conanfile.settings
    settings_build = conanfile.settings_build

    arch_host = str(settings_host.arch)
    arch_build = str(settings_build.arch)

    arch = None
    if arch_build == 'x86_64':
        arch = {'x86': "amd64_x86",
                'x86_64': 'amd64',
                'armv7': 'amd64_arm',
                'armv8': 'amd64_arm64'}.get(arch_host)
    elif arch_build == 'x86':
        arch = {'x86': 'x86',
                'x86_64': 'x86_amd64',
                'armv7': 'x86_arm',
                'armv8': 'x86_arm64'}.get(arch_host)

    if not arch:
        raise ConanException('vcvars unsupported architectures %s-%s' % (arch_build, arch_host))

    return arch
