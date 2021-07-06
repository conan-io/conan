from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.client.tools.win import vcvars_dict


class VirtualBuildEnvGenerator(VirtualEnvGenerator):

    suffix = "_build"
    venv_name = "conanbuildenv"

    def __init__(self, conanfile):
        super(VirtualBuildEnvGenerator, self).__init__(conanfile)
        compiler = conanfile.settings.get_safe("compiler")
        if compiler == "Visual Studio":
            settings_vars = vcvars_dict(conanfile.settings, output=conanfile.output)
            # self.env has higher priority, so only extend (append) to it.
            for name, value in self.env.items():
                if isinstance(value, list):
                    value.extend(settings_vars.pop(name, []))

            self.env.update(settings_vars)
