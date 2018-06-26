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
            vcvars_env = {}
            for var_name, var_value in vcvars_dict(conanfile.settings).items():
                old_value = os.environ.get(var_name)
                if old_value != var_value:
                    if old_value is not None and old_value in var_value:
                        new_value = var_value.replace(old_value, "")
                        vcvars_env[var_name] = new_value + "%{0}%".format(var_name)
                    else:
                        vcvars_env[var_name] = var_value
            self.env.update(vcvars_env)
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
