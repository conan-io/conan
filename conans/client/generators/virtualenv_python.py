from conans.client.generators.virtualrunenv import VirtualRunEnvGenerator


def _python_paths(deps_env_info):
    result = set()
    for dep in deps_env_info.deps:
        result.update(deps_env_info[dep].vars.get("PYTHONPATH", set()))

    return list(result)


class VirtualEnvPythonGenerator(VirtualRunEnvGenerator):
    def __init__(self, conanfile):
        super(VirtualEnvPythonGenerator, self).__init__(conanfile)
        self.venv_name = "conanenvpython"
        self.env["PYTHONPATH"] = _python_paths(self.conanfile.deps_env_info)
