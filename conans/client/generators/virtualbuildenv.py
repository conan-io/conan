from conans.client.configure_build_environment import (AutoToolsBuildEnvironment, VisualStudioBuildEnvironment)
from conans.client.generators.virtualenv import VirtualEnvGenerator


class VirtualBuildEnvGenerator(VirtualEnvGenerator):

    def __init__(self, conanfile):
        super(VirtualBuildEnvGenerator, self).__init__(conanfile)
        compiler = conanfile.settings.get_safe("compiler")
        if compiler != "Visual Studio":
            tools = AutoToolsBuildEnvironment(conanfile)
        else:
            tools = VisualStudioBuildEnvironment(conanfile)

        self.env = tools.vars_dict

    @property
    def content(self):
        tmp = super(VirtualBuildEnvGenerator, self).content
        ret = {}
        for name, value in tmp.items():
            tmp = name.split(".")
            ret["%s_build.%s" % (tmp[0], tmp[1])] = value

        return ret
