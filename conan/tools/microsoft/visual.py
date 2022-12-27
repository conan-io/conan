import os
import textwrap

from conan.internal import check_duplicated_generator
from conans.client.conf.detect_vs import vs_installation_path
from conans.errors import ConanException, ConanInvalidConfiguration
from conan.tools.scm import Version

CONAN_VCVARS_FILE = "conanvcvars.bat"


def check_min_vs(conanfile, version):
    """
    This is a helper method to allow the migration of 1.X -> 2.0 and VisualStudio -> msvc settings
    without breaking recipes.
    The legacy "Visual Studio" with different toolset is not managed, not worth the complexity.

    :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
    :param version: ``str`` Visual Studio or msvc version number.
    """
    compiler = conanfile.settings.get_safe("compiler")
    compiler_version = None
    if compiler == "Visual Studio":
        compiler_version = conanfile.settings.get_safe("compiler.version")
        compiler_version = {"17": "193",
                            "16": "192",
                            "15": "191",
                            "14": "190",
                            "12": "180",
                            "11": "170"}.get(compiler_version)
    elif compiler == "msvc":
        compiler_version = conanfile.settings.get_safe("compiler.version")
        compiler_update = conanfile.settings.get_safe("compiler.update")
        if compiler_version and compiler_update is not None:
            compiler_version += ".{}".format(compiler_update)

    if compiler_version and Version(compiler_version) < version:
        msg = "This package doesn't work with VS compiler version '{}'" \
              ", it requires at least '{}'".format(compiler_version, version)
        raise ConanInvalidConfiguration(msg)


def msvc_version_to_vs_ide_version(version):
    """
    Gets the Visual Studio IDE version given the ``msvc`` compiler one.

    :param version: ``str`` or ``int`` msvc version
    :return: VS IDE version
    """
    _visuals = {'170': '11',
                '180': '12',
                '190': '14',
                '191': '15',
                '192': '16',
                '193': '17'}
    return _visuals[str(version)]


def msvc_version_to_toolset_version(version):
    """
    Gets the Visual Studio IDE toolset version given the ``msvc`` compiler one.

    :param version: ``str`` or ``int`` msvc version
    :return: VS IDE toolset version
    """
    toolsets = {'170': 'v110',
                '180': 'v120',
                '190': 'v140',
                '191': 'v141',
                '192': 'v142',
                "193": 'v143'}
    return toolsets[str(version)]


class VCVars:
    """
    VCVars class generator
    """

    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        self._conanfile = conanfile

    def generate(self, scope="build"):
        """
        Creates a ``conanvcvars.bat`` file with the good args from settings to set environment
        variables to configure the command line for native 32-bit or 64-bit compilation.

        :param scope: ``str`` Launcher to be used to run all the variables. For instance,
                      if ``build``, then it'll be used the ``conanbuild`` launcher.
        """
        check_duplicated_generator(self, self._conanfile)
        conanfile = self._conanfile
        os_ = conanfile.settings.get_safe("os")
        if os_ != "Windows":
            return

        compiler = conanfile.settings.get_safe("compiler")
        if compiler not in ("msvc", "clang"):
            return

        if compiler == "clang":
            # The vcvars only needed for LLVM/Clang and VS ClangCL, who define runtime
            if not conanfile.settings.get_safe("compiler.runtime"):
                # NMake Makefiles will need vcvars activated, for VS target, defined with runtime
                return
            toolset_version = conanfile.settings.get_safe("compiler.runtime_version")
            vs_version = {"v140": "14",
                          "v141": "15",
                          "v142": "16",
                          "v143": "17"}.get(toolset_version)
            if vs_version is None:
                raise ConanException("Visual Studio Runtime version (v140-v143) not defined")
            vcvars_ver = {"v140": "14.0",
                          "v141": "14.1",
                          "v142": "14.2",
                          "v143": "14.3"}.get(toolset_version)
        else:
            vs_version = vs_ide_version(conanfile)
            vcvars_ver = _vcvars_vers(conanfile, compiler, vs_version)
        vcvarsarch = _vcvars_arch(conanfile)

        vs_install_path = conanfile.conf.get("tools.microsoft.msbuild:installation_path")
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
    """
    Gets the VS IDE version as string. It'll use the ``compiler.version`` (if exists) and/or the
    ``tools.microsoft.msbuild:vs_version`` if ``compiler`` is ``msvc``.

    :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
    :return: ``str`` Visual IDE version number.
    """
    compiler = conanfile.settings.get_safe("compiler")
    compiler_version = conanfile.settings.get_safe("compiler.version")
    if compiler == "msvc":
        toolset_override = conanfile.conf.get("tools.microsoft.msbuild:vs_version", check_type=str)
        if toolset_override:
            visual_version = toolset_override
        else:
            visual_version = msvc_version_to_vs_ide_version(compiler_version)
    else:
        visual_version = compiler_version
    return visual_version


def msvc_runtime_flag(conanfile):
    """
    Gets the MSVC runtime flag given the ``compiler.runtime`` value from the settings.

    :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
    :return: ``str`` runtime flag.
    """
    settings = conanfile.settings
    runtime = settings.get_safe("compiler.runtime")
    if runtime is not None:
        if runtime == "static":
            runtime = "MT"
        elif runtime == "dynamic":
            runtime = "MD"
        else:
            raise ConanException("compiler.runtime should be 'static' or 'dynamic'")
        runtime_type = settings.get_safe("compiler.runtime_type")
        if runtime_type == "Debug":
            runtime = "{}d".format(runtime)
        return runtime
    return ""


def vcvars_command(version, architecture=None, platform_type=None, winsdk_version=None,
                   vcvars_ver=None, start_dir_cd=True, vs_install_path=None):
    """
    Conan-agnostic construction of vcvars command
    https://docs.microsoft.com/en-us/cpp/build/building-on-the-command-line

    :param version: ``str`` Visual Studio version.
    :param architecture: ``str`` Specifies the host and target architecture to use.
    :param platform_type: ``str`` Allows you to specify ``store`` or ``uwp`` as the platform type.
    :param winsdk_version: ``str`` Specifies the version of the Windows SDK to use.
    :param vcvars_ver: ``str`` Specifies the Visual Studio compiler toolset to use.
    :param start_dir_cd: ``bool`` If ``True``, the command will execute
                         ``set "VSCMD_START_DIR=%CD%`` at first.
    :param vs_install_path: ``str`` Visual Studio installation path.
    :return: ``str`` complete _vcvarsall_ command.
    """
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


def _vcvars_arch(conanfile):
    """
    Computes the vcvars command line architecture based on conanfile settings (host) and
    settings_build.
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
    elif arch_build == 'armv8':
        arch = {'x86': 'arm64_x86',
                'x86_64': 'arm64_x64',
                'armv7': 'arm64_arm',
                'armv8': 'arm64'}.get(arch_host)

    if not arch:
        raise ConanException('vcvars unsupported architectures %s-%s' % (arch_build, arch_host))

    return arch


def _vcvars_vers(conanfile, compiler, vs_version):
    if int(vs_version) <= 14:
        return None

    assert compiler == "msvc"
    # Code similar to CMakeToolchain toolset one
    compiler_version = str(conanfile.settings.compiler.version)
    # The equivalent of compiler 192 is toolset 14.2
    vcvars_ver = "14.{}".format(compiler_version[-1])
    return vcvars_ver


def is_msvc(conanfile, build_context=False):
    """
    Validates if the current compiler is ``msvc``.

    :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
    :param build_context: If True, will use the settings from the build context, not host ones
    :return: ``bool`` True, if the host compiler is ``msvc``, otherwise, False.
    """
    if not build_context:
        settings = conanfile.settings
    else:
        settings = conanfile.settings_build
    return settings.get_safe("compiler") == "msvc"


def is_msvc_static_runtime(conanfile):
    """
    Validates when building with Visual Studio or msvc and MT on runtime.

    :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
    :return: ``bool`` True, if ``msvc + runtime MT``. Otherwise, False.
    """
    return is_msvc(conanfile) and "MT" in msvc_runtime_flag(conanfile)
