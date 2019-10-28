from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.client.run_environment import RunEnvironment


class VirtualRunEnvGenerator(VirtualEnvGenerator):
    environment_filename = "environment_run.env"

    def __init__(self, conanfile):
        super(VirtualRunEnvGenerator, self).__init__(conanfile)
        self.venv_name = "conanrunenv"
        run_env = RunEnvironment(conanfile)
        self.env = run_env.vars

    @property
    def content(self):
        tmp = super(VirtualRunEnvGenerator, self).content
        ret = {}
        for name, value in tmp.items():
            if name != self.environment_filename:
                tmp = name.split(".")
                ret["%s_run.%s" % (tmp[0], tmp[1])] = value
            else:
                ret[name] = value

        return ret
