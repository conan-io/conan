from conans.client.build.autotools_environment import AutoToolsBuildEnvironment
from conans.client.build.visual_environment import VisualStudioBuildEnvironment
from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.client.tools.win import vcvars_dict


class VirtualBuildEnvGenerator(VirtualEnvGenerator):
    environment_filename = "environment_build.env"

    def __init__(self, conanfile):
        super(VirtualBuildEnvGenerator, self).__init__(conanfile)
        self.venv_name = "conanbuildenv"
        compiler = conanfile.settings.get_safe("compiler")
        if compiler == "Visual Studio":
            self.env = VisualStudioBuildEnvironment(conanfile).vars_dict
            settings_vars = vcvars_dict(conanfile.settings, output=conanfile.output)
            # self.env has higher priority, so only extend (append) to it.
            for name, value in self.env.items():
                if isinstance(value, list):
                    value.extend(settings_vars.pop(name, []))

            self.env.update(settings_vars)
        else:
            self.env = AutoToolsBuildEnvironment(conanfile).vars_dict

    @property
    def content(self):
        tmp = super(VirtualBuildEnvGenerator, self).content
        ret = {}
        for name, value in tmp.items():
            if name != self.environment_filename:
                tmp = name.split(".")
                ret["%s_build.%s" % (tmp[0], tmp[1])] = value
            else:
                ret[name] = value
        return ret
