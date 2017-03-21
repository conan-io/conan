import platform

from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.client.configure_build_environment import (AutoToolsBuildEnvironment, VisualStudioBuildEnvironment)


class VirtualBuildEnvGenerator(VirtualEnvGenerator):

    def __init__(self, conanfile):
        super(VirtualBuildEnvGenerator, self).__init__(conanfile)

        compiler = conanfile.settings.get_safe("compiler")
        self.env = {}
        if compiler != "Visual Studio":
            auto_tools_b = AutoToolsBuildEnvironment(conanfile)
            tmp = {var: '%s' % value for var, value in auto_tools_b.vars.items()}
            self.env = tmp
        else:
            visual_b = VisualStudioBuildEnvironment(conanfile, quote_paths=False)
            self.env = visual_b.vars

    @property
    def content(self):
        tmp = super(VirtualBuildEnvGenerator, self).content
        ret = {}
        for name, value in tmp.items():
            tmp = name.split(".")
            ret["%s_build.%s" % (tmp[0], tmp[1])] = value

        return ret
