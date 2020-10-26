import os

from conans.client.tools.win import vs_installation_path
from conans.errors import ConanException


def vcvars_command(version, architecture=None, platform_type=None, winsdk_version=None,
                   vcvars_ver=None, start_dir_cd=True):
    """ conan-agnostic construction of vcvars command
    https://docs.microsoft.com/en-us/cpp/build/building-on-the-command-line
    """
    # TODO: This comes from conans/client/tools/win.py vcvars_command()
    cmd = []
    if start_dir_cd:
        cmd.append('set "VSCMD_START_DIR=%%CD%%" &&')

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
    # TODO: This comes from conans/client/tools/win.py vcvars_command()
    settings_host = conanfile.settings
    try:
        settings_build = conanfile.settings_build
    except AttributeError:
        settings_build = settings_host

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
