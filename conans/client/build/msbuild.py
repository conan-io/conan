import copy
import re

from conans import tools
from conans.client.build.visual_environment import (VisualStudioBuildEnvironment,
                                                    vs_build_type_flags, vs_std_cpp)
from conans.client.tools.oss import cpu_count
from conans.client.tools.win import vcvars_command
from conans.errors import ConanException
from conans.util.env_reader import get_env
from conans.util.files import tmp_file
from conans.model.conan_file import ConanFile


class MSBuild(object):

    def __init__(self, conanfile):
        if isinstance(conanfile, ConanFile):
            self._conanfile = conanfile
            self._settings = self._conanfile.settings
            self._output = self._conanfile.output
            self.build_env = VisualStudioBuildEnvironment(self._conanfile)
        else:  # backwards compatible with build_sln_command
            self._settings = conanfile
            self.build_env = None

    def build(self, project_file, targets=None, upgrade_project=True, build_type=None, arch=None,
              parallel=True, force_vcvars=False, toolset=None, platforms=None, use_env=True,
              vcvars_ver=None, winsdk_version=None, properties=None):

        self.build_env.parallel = parallel

        with tools.environment_append(self.build_env.vars):
            # Path for custom properties file
            props_file_contents = self._get_props_file_contents()
            with tmp_file(props_file_contents) as props_file_path:
                vcvars = vcvars_command(self._conanfile.settings, force=force_vcvars,
                                        vcvars_ver=vcvars_ver, winsdk_version=winsdk_version)
                command = self.get_command(project_file, props_file_path,
                                           targets=targets, upgrade_project=upgrade_project,
                                           build_type=build_type, arch=arch, parallel=parallel,
                                           toolset=toolset, platforms=platforms,
                                           use_env=use_env, properties=properties)
                command = "%s && %s" % (vcvars, command)
                return self._conanfile.run(command)

    def get_command(self, project_file, props_file_path=None, targets=None, upgrade_project=True,
                    build_type=None, arch=None, parallel=True, toolset=None, platforms=None,
                    use_env=False, properties=None):

        targets = targets or []
        properties = properties or {}
        command = []

        if upgrade_project and not get_env("CONAN_SKIP_VS_PROJECTS_UPGRADE", False):
            command.append('devenv "%s" /upgrade &&' % project_file)
        else:
            self._output.info("Skipped sln project upgrade")

        build_type = build_type or self._settings.get_safe("build_type")
        arch = arch or self._settings.get_safe("arch")
        if not build_type:
            raise ConanException("Cannot build_sln_command, build_type not defined")
        if not arch:
            raise ConanException("Cannot build_sln_command, arch not defined")

        command.append('msbuild "%s" /p:Configuration="%s"' % (project_file, build_type))
        msvc_arch = {'x86': 'x86',
                     'x86_64': 'x64',
                     'armv7': 'ARM',
                     'armv8': 'ARM64'}
        if platforms:
            msvc_arch.update(platforms)
        msvc_arch = msvc_arch.get(str(arch))
        try:
            sln = tools.load(project_file)
            pattern = re.compile(r"GlobalSection\(SolutionConfigurationPlatforms\)"
                                 r"(.*?)EndGlobalSection", re.DOTALL)
            solution_global = pattern.search(sln).group(1)
            lines = solution_global.splitlines()
            lines = [s.split("=")[0].strip() for s in lines]
        except Exception:
            pass
        else:
            config = "%s|%s" % (build_type, msvc_arch)
            if config not in "".join(lines):
                self._output.warn("***** The configuration %s does not exist in this solution *****" % config)
                self._output.warn("Use 'platforms' argument to define your architectures")

        if use_env:
            command.append('/p:UseEnv=true')

        if msvc_arch:
            command.append('/p:Platform="%s"' % msvc_arch)

        if parallel:
            command.append('/m:%s' % cpu_count())

        if targets:
            command.append("/target:%s" % ";".join(targets))

        if toolset:
            command.append('/p:PlatformToolset="%s"' % toolset)

        if props_file_path:
            command.append('/p:ForceImportBeforeCppTargets="%s"' % props_file_path)

        for name, value in properties.items():
            command.append('/p:%s="%s"' % (name, value))

        return " ".join(command)

    def _get_props_file_contents(self):
        # how to specify runtime in command line:
        # https://stackoverflow.com/questions/38840332/msbuild-overrides-properties-while-building-vc-project
        runtime_library = {"MT": "MultiThreaded",
                           "MTd": "MultiThreadedDebug",
                           "MD": "MultiThreadedDLL",
                           "MDd": "MultiThreadedDebugDLL"}.get(self._settings.get_safe("compiler.runtime"), "")

        if self.build_env:
            # Take the flags from the build env, the user was able to alter them if needed
            flags = copy.copy(self.build_env.flags)
            flags.append(self.build_env.std)
        else:  # To be removed when build_sln_command is deprecated
            flags = vs_build_type_flags(self._settings)
            flags.append(vs_std_cpp(self._settings))

        flags_str = " ".join(list(filter(None, flags))) # Removes empty and None elements
        additional_node = "<AdditionalOptions>" \
                          "{} %(AdditionalOptions)" \
                          "</AdditionalOptions>".format(flags_str) if flags_str else ""
        runtime_node = "<RuntimeLibrary>" \
                       "{}" \
                       "</RuntimeLibrary>".format(runtime_library) if runtime_library else ""
        template = """<?xml version="1.0" encoding="utf-8"?>
<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemDefinitionGroup>
    <ClCompile>
      {runtime_node}
      {additional_node}
    </ClCompile>
  </ItemDefinitionGroup>
</Project>""".format(**{"runtime_node": runtime_node,
                        "additional_node": additional_node})
        return template
