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
            # We append the list, so the parent virtualenv generator will append the current environment
            # values and automatically merge this variables with spaces, because we are adding the keys
            # to "append_with_spaces"
            vars_list = auto_tools_b.vars_list
            self.append_with_spaces.extend(vars_list.keys())
            self.env = vars_list
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
