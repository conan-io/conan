from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.model.settings import get_setting_str_safe


class VirtualBuildEnvGenerator(VirtualEnvGenerator):

    def __init__(self, conanfile):
        super(VirtualBuildEnvGenerator, self).__init__(conanfile)
        from conans.client.configure_build_environment import AutoToolsBuildEnvironment, GCCBuildEnvironment, \
            VisualStudioBuildEnvironment
        compiler = get_setting_str_safe(conanfile.settings, "compiler")
        self.env = {}
        if compiler != "VisualStudio":
            auto_tools_b = AutoToolsBuildEnvironment(conanfile)
            gcc_b = GCCBuildEnvironment(conanfile)
            tmp = auto_tools_b.vars
            tmp.update(gcc_b.vars)
            self.env = tmp
        else:
            visual_b = VisualStudioBuildEnvironment(conanfile)
            self.env = visual_b.vars


    @property
    def content(self):
        tmp = super(VirtualBuildEnvGenerator, self).content
        ret = {"activate_build.bat": tmp["activate.bat"],
               "deactivate_build.bat": tmp["deactivate.bat"],
               "activate_build.ps1": tmp["activate.ps1"],
               "deactivate_build.ps1": tmp["deactivate.ps1"]}
        return ret
