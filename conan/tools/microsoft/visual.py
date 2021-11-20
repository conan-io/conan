import os
import textwrap

from conans.client.tools import vs_installation_path
from conans.errors import ConanException

CONAN_VCVARS_FILE = "conanvcvars.bat"


def msvc_version_to_vs_ide_version(version):
    _visuals = {'190': '14',
                '191': '15',
                '192': '16',
                '193': '17'}
    return _visuals[str(version)]


class VCVars:
    def __init__(self, conanfile):
        self._conanfile = conanfile

    def generate(self, scope="build"):
        """
        write a conanvcvars.bat file with the good args from settings
        """
        conanfile = self._conanfile
        os_ = conanfile.settings.get_safe("os")
        if os_ != "Windows":
            return

        compiler = conanfile.settings.get_safe("compiler")
        if compiler != "Visual Studio" and compiler != "msvc":
            return

        vs_version = vs_ide_version(conanfile)
        vcvarsarch = vcvars_arch(conanfile)
        vcvars_ver = _vcvars_vers(conanfile, compiler, vs_version)

        vs_install_path = conanfile.conf["tools.microsoft.msbuild:installation_path"]
        # The vs_install_path is like
        # C:\Program Files (x86)\Microsoft Visual Studio\2019\Community
        # C:\Program Files (x86)\Microsoft Visual Studio\2017\Community
        # C:\Program Files (x86)\Microsoft Visual Studio 14.0
        vcvars = vcvars_command(vs_version, architecture=vcvarsarch, platform_type=None,
                                winsdk_version=None, vcvars_ver=vcvars_ver,
                                vs_install_path=vs_install_path)

        content = textwrap.dedent("""\
            @echo off
            {}
            """.format(vcvars))
        from conan.tools.env.environment import create_env_script
        create_env_script(conanfile, content, CONAN_VCVARS_FILE, scope)


def vs_ide_version(conanfile):
    compiler = conanfile.settings.get_safe("compiler")
    compiler_version = (conanfile.settings.get_safe("compiler.base.version") or
                        conanfile.settings.get_safe("compiler.version"))
    if compiler == "msvc":
        toolset_override = conanfile.conf["tools.microsoft.msbuild:vs_version"]
        if toolset_override:
            visual_version = toolset_override
        else:
            visual_version = msvc_version_to_vs_ide_version(compiler_version)
    else:
        visual_version = compiler_version
    return visual_version


def msvc_runtime_flag(conanfile):
    settings = conanfile.settings
    compiler = settings.get_safe("compiler")
    runtime = settings.get_safe("compiler.runtime")
    if compiler == "Visual Studio":
        return runtime
    if compiler == "msvc" or compiler == "intel-cc":
        runtime_type = settings.get_safe("compiler.runtime_type")
        runtime = "MT" if runtime == "static" else "MD"
        if runtime_type == "Debug":
            runtime = "{}d".format(runtime)
        return runtime


def vcvars_command(version, architecture=None, platform_type=None, winsdk_version=None,
                   vcvars_ver=None, start_dir_cd=True, vs_install_path=None):
    """ conan-agnostic construction of vcvars command
    https://docs.microsoft.com/en-us/cpp/build/building-on-the-command-line
    """
    # TODO: This comes from conans/client/tools/win.py vcvars_command()
    cmd = []
    if start_dir_cd:
        cmd.append('set "VSCMD_START_DIR=%CD%" &&')

    # The "call" is useful in case it is called from another .bat script
    cmd.append('call "%s" ' % _vcvars_path(version, vs_install_path))
    if architecture:
        cmd.append(architecture)
    if platform_type:
        cmd.append(platform_type)
    if winsdk_version:
        cmd.append(winsdk_version)
    if vcvars_ver:
        cmd.append("-vcvars_ver=%s" % vcvars_ver)
    return " ".join(cmd)


def _vcvars_path(version, vs_install_path):
    # TODO: This comes from conans/client/tools/win.py vcvars_command()
    vs_path = vs_install_path or vs_installation_path(version)
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


def _vcvars_vers(conanfile, compiler, vs_version):
    if int(vs_version) <= 14:
        return None

    vcvars_ver = None
    if compiler == "Visual Studio":
        toolset = conanfile.settings.get_safe("compiler.toolset")
        if toolset is not None:
            vcvars_ver = {"v140": "14.0",
                          "v141": "14.1",
                          "v142": "14.2",
                          "v143": "14.3"}.get(toolset)
    else:
        assert compiler == "msvc"
        # Code similar to CMakeToolchain toolset one
        compiler_version = str(conanfile.settings.compiler.version)
        # The equivalent of compiler 192 is toolset 14.2
        vcvars_ver = "14.{}".format(compiler_version[-1])
    return vcvars_ver
