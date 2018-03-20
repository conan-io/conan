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
                                         platforms=platforms)
            return self._conanfile.run(command)
