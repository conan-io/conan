import os

from conan.tools.microsoft.msbuilddeps import MSBuildDeps
from conan.tools.microsoft.toolchain import MSBuildToolchain
from conan.tools.microsoft.visual import msvs_toolset
from conans.errors import ConanException


def msbuild_verbosity_cmd_line_arg(conanfile):
    verbosity = conanfile.conf.get("tools.microsoft.msbuild:verbosity")
    if verbosity:
        if verbosity not in ("Quiet", "Minimal", "Normal", "Detailed", "Diagnostic"):
            raise ConanException("Unknown msbuild verbosity: {}".format(verbosity))
        return '/verbosity:{}'.format(verbosity)


def msbuild_arch(arch):
    return {'x86': 'x86',
            'x86_64': 'x64',
            'armv7': 'ARM',
            'armv8': 'ARM64'}.get(str(arch))


class MSBuild(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.build_type = conanfile.settings.get_safe("build_type")
        # if platforms:
        #    msvc_arch.update(platforms)
        arch = conanfile.settings.get_safe("arch")
        msvc_arch = msbuild_arch(arch)
        if conanfile.settings.get_safe("os") == "WindowsCE":
            msvc_arch = conanfile.settings.get_safe("os.platform")
        self.platform = msvc_arch
        self.toolset = msvs_toolset(conanfile)

    def command(self, sln, targets=None, auto_inject_deps_props=True):
        cmd = (f'msbuild "{sln}" /p:Configuration={self.build_type} '
               f"/p:Platform={self.platform} /p:PlatformToolset={self.toolset}")

        # Autoconsume toolchain props, but opt-out dependencies props
        props_paths = []
        props_candidates = [MSBuildToolchain.filename]
        if auto_inject_deps_props:
            props_candidates.append(MSBuildDeps.filename)
        for props_file in props_candidates:
            props_path = os.path.join(self._conanfile.generators_folder, props_file)
            if os.path.exists(props_path):
                props_paths.append(props_path)
        if props_paths:
            props_paths = ";".join(props_paths)
            cmd += f" /p:ForceImportBeforeCppTargets=\"{props_paths}\""

        verbosity = msbuild_verbosity_cmd_line_arg(self._conanfile)
        if verbosity:
            cmd += " {}".format(verbosity)

        maxcpucount = self._conanfile.conf.get("tools.microsoft.msbuild:max_cpu_count",
                                               check_type=int)
        if maxcpucount:
            cmd += " /m:{}".format(maxcpucount)

        if targets:
            if not isinstance(targets, list):
                raise ConanException("targets argument should be a list")
            cmd += " /target:{}".format(";".join(targets))

        return cmd

    def build(self, sln, targets=None, auto_inject_deps_props=True):
        cmd = self.command(sln, targets=targets, auto_inject_deps_props=auto_inject_deps_props)
        self._conanfile.run(cmd)

    @staticmethod
    def get_version(_):
        return NotImplementedError("get_version() method is not supported in MSBuild "
                                   "toolchain helper")
