import os

from conans import tools
from conans.client.build.visual_environment import VisualStudioBuildEnvironment
from conans.client.tools.win import msvc_build_command


class MSBuild(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.build_env = VisualStudioBuildEnvironment(self._conanfile)

    def build(self, project_file, targets=None, upgrade_project=True, build_type=None, arch=None,
              parallel=True, force_vcvars=False, toolset=None, platforms=None):
        with tools.environment_append(self.build_env.vars):
            command = msvc_build_command(self._conanfile.settings,
                                         project_file, targets=targets,
                                         upgrade_project=upgrade_project,
                                         build_type=build_type, arch=arch, parallel=parallel,
                                         force_vcvars=force_vcvars, toolset=toolset,
                                         platforms=platforms,
                                         use_env=True)
            runtime = self._conanfile.settings.get_safe("compiler.runtime")
            # Rel path is ignored, so make it abs
            overrides_path = os.path.join(os.getcwd(), ".conan_overrides.props")
            if runtime:
                # how to specify runtime in command line:
                # https://stackoverflow.com/questions/38840332/msbuild-overrides-properties-while-building-vc-project
                runtime_library = {"MT": "MultiThreaded",
                                  "MTd": "MultiThreadedDebug",
                                  "MD": "MultiThreadedDLL",
                                  "MDd": "MultiThreadedDebugDLL"}[runtime]
                template = """<?xml version="1.0" encodinog="utf-8"?>
<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemDefinitionGroup>
    <ClCompile>
      <RuntimeLibrary>%s</RuntimeLibrary>
    </ClCompile>
  </ItemDefinitionGroup>
</Project>""" % runtime_library
                tools.save(overrides_path, template)
                command += ' /p:ForceImportBeforeCppTargets="%s"' % overrides_path

            ret = self._conanfile.run(command)

            try:
                if os.path.exists(overrides_path):
                    os.unlink(overrides_path)
            except Exception:
                pass
            return ret