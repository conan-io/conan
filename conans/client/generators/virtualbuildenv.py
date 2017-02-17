import platform

from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.model.settings import get_setting_str_safe
from conans.client.configure_build_environment import (AutoToolsBuildEnvironment, GCCBuildEnvironment,
                                                       VisualStudioBuildEnvironment)


class VirtualBuildEnvGenerator(VirtualEnvGenerator):

    def __init__(self, conanfile):
        super(VirtualBuildEnvGenerator, self).__init__(conanfile)

        compiler = get_setting_str_safe(conanfile.settings, "compiler")
        self.env = {}
        if compiler != "VisualStudio":
            auto_tools_b = AutoToolsBuildEnvironment(conanfile)
            gcc_b = GCCBuildEnvironment(conanfile)
            tmp = {var: '"%s"' % value for var, value in auto_tools_b.vars.items()}
            tmp2 = {var: '"%s"' % value for var, value in gcc_b.vars.items()}
            tmp.update(tmp2)
            self.env = tmp
        else:
            visual_b = VisualStudioBuildEnvironment(conanfile)
            self.env = visual_b.vars

    @property
    def content(self):
        tmp = super(VirtualBuildEnvGenerator, self).content
        ret = {}
        for name, value in tmp.items():
            tmp = name.split(".")
            ret["%s_build.%s" % (tmp[0], tmp[1])] = value

        return ret
