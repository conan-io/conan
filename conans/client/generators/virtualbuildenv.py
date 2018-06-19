import os

from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.client.build.autotools_environment import AutoToolsBuildEnvironment
from conans.client.build.visual_environment import VisualStudioBuildEnvironment
from conans.tools import vcvars_dict


class VirtualBuildEnvGenerator(VirtualEnvGenerator):

    def __init__(self, conanfile):
        super(VirtualBuildEnvGenerator, self).__init__(conanfile)
        self.venv_name = "conanbuildenv"
        compiler = conanfile.settings.get_safe("compiler")
        if compiler == "Visual Studio":
            self.env = VisualStudioBuildEnvironment(conanfile).vars_dict
            vcvars = vcvars_dict(conanfile.settings)
            vcvars["PATH"] = vcvars["PATH"].replace(os.environ["PATH"], "") + "%PATH%;"
            self.env.update(vcvars)
        else:
            self.env = AutoToolsBuildEnvironment(conanfile).vars_dict

    @property
    def content(self):
        tmp = super(VirtualBuildEnvGenerator, self).content
        ret = {}
        for name, value in tmp.items():
            tmp = name.split(".")
            ret["%s_build.%s" % (tmp[0], tmp[1])] = value

        return ret
