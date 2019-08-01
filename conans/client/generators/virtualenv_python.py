from conans.client.generators.virtualrunenv import VirtualRunEnvGenerator


class VirtualEnvPythonGenerator(VirtualRunEnvGenerator):
    def __init__(self, conanfile):
        super(VirtualEnvPythonGenerator, self).__init__(conanfile)
        self.venv_name = "conanenvpython"
        self.env["PYTHONPATH"] = list(
            set(
                conanfile.env.get("PYTHONPATH", [])
                + self.deps_env_info.vars.get("PYTHONPATH", [])
            )
        )
