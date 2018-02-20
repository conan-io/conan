from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.client.build.autotools_environment import AutoToolsBuildEnvironment
from conans.client.build.visual_environment import VisualStudioBuildEnvironment


class VirtualBuildEnvGenerator(VirtualEnvGenerator):

    def __init__(self, conanfile):
        super(VirtualBuildEnvGenerator, self).__init__(conanfile)
        self.venv_name = "conanbuildenv"
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
