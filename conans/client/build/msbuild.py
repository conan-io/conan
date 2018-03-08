import re

from conans import tools
from conans.client.build.visual_environment import VisualStudioBuildEnvironment
from conans.client.tools.oss import cpu_count
from conans.client.tools.win import vcvars_command
from conans.errors import ConanException
from conans.util.env_reader import get_env


class MSBuild(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.build_env = VisualStudioBuildEnvironment(self._conanfile)

    def build(self, project_file, targets=None, upgrade_project=True, build_type=None, arch=None,
              parallel=True, force_vcvars=False, toolset=None, platforms=None):
        with tools.environment_append(self.build_env.vars):
            # Path for custom properties file
            props_file_contents = _get_props_file_contents(self._conanfile.settings)
            builder = _MSBuildCommandBuilder(self._conanfile.settings, self._conanfile.output)
            with tools.tmp_file(props_file_contents) as props_file_path:
                vcvars = vcvars_command(self._conanfile.settings, force=force_vcvars)
                command = builder.get_command(project_file, props_file_path,
                                              targets=targets, upgrade_project=upgrade_project,
                                              build_type=build_type, arch=arch, parallel=parallel,
                                              toolset=toolset, platforms=platforms,
                                              use_env=True)
                command = "%s && %s" % (vcvars, command)
                return self._conanfile.run(command)


class _MSBuildCommandBuilder(object):
    """Can't be merged with MSBuild(), thing that sounds reasonable because it is used by the tools build_sln_command
    where we don't have the conanfile but the settings. Idea: Deprecate these tools in favor of the MSBuild(),
     merge when removed in 2.0"""

    def __init__(self, settings, output):
        self._settings = settings
        self._output = output

    def get_command(self, sln_path, props_file_path, targets=None, upgrade_project=True, build_type=None,
                    arch=None, parallel=True, toolset=None, platforms=None, use_env=False):

        targets = targets or []
        command = ""

        if upgrade_project and not get_env("CONAN_SKIP_VS_PROJECTS_UPGRADE", False):
            command += "devenv %s /upgrade && " % sln_path
        else:
            self.output.info("Skipped sln project upgrade")

        build_type = build_type or self._settings.build_type
        arch = arch or self._settings.arch
        if not build_type:
            raise ConanException("Cannot build_sln_command, build_type not defined")
        if not arch:
            raise ConanException("Cannot build_sln_command, arch not defined")
        command += "msbuild  %s /p:Configuration=%s" % (sln_path, build_type)
        msvc_arch = {'x86': 'x86',
                     'x86_64': 'x64',
                     'armv7': 'ARM',
                     'armv8': 'ARM64'}
        if platforms:
            msvc_arch.update(platforms)
        msvc_arch = msvc_arch.get(str(arch))
        try:
            sln = tools.load(sln_path)
            pattern = re.compile(r"GlobalSection\(SolutionConfigurationPlatforms\)(.*?)EndGlobalSection", re.DOTALL)
            solution_global = pattern.search(sln).group(1)
            lines = solution_global.splitlines()
            lines = [s.split("=")[0].strip() for s in lines]
        except Exception:
            pass
        else:
            config = "%s|%s" % (build_type, msvc_arch)
            if config not in "".join(lines):
                self.output.warn("***** The configuration %s does not exist in this solution *****" % config)
                self.output.warn("Use 'platforms' argument to define your architectures")

        if use_env:
            command += ' /p:UseEnv=true'

        if msvc_arch:
            command += ' /p:Platform="%s"' % msvc_arch

        if parallel:
            command += ' /m:%s' % cpu_count()

        if targets:
            command += " /target:%s" % ";".join(targets)

        if toolset:
            command += " /p:PlatformToolset=%s" % toolset

        command += ' /p:ForceImportBeforeCppTargets="%s"' % props_file_path

        return command


def _get_props_file_contents(settings):
    runtime = settings.get_safe("compiler.runtime")
    # Rel path is ignored, so make it abs
    if runtime:
        # how to specify runtime in command line:
        # https://stackoverflow.com/questions/38840332/msbuild-overrides-properties-while-building-vc-project
        runtime_library = {"MT": "MultiThreaded",
                          "MTd": "MultiThreadedDebug",
                          "MD": "MultiThreadedDLL",
                          "MDd": "MultiThreadedDebugDLL"}[runtime]
        template = """<?xml version="1.0" encoding="utf-8"?>
<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemDefinitionGroup>
    <ClCompile>
      <RuntimeLibrary>%s</RuntimeLibrary>
    </ClCompile>
  </ItemDefinitionGroup>
</Project>""" % runtime_library
        return template

    return ""