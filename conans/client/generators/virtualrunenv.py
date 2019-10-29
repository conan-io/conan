from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.client.run_environment import RunEnvironment


class VirtualRunEnvGenerator(VirtualEnvGenerator):

    suffix = "_run"
    venv_name = "conanrunenv"

    def __init__(self, conanfile):
        super(VirtualRunEnvGenerator, self).__init__(conanfile)
        run_env = RunEnvironment(conanfile)
        self.env = run_env.vars
