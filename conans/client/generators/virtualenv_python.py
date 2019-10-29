from conans.client.generators.virtualrunenv import VirtualRunEnvGenerator


class VirtualEnvPythonGenerator(VirtualRunEnvGenerator):

    suffix = "_python"
    venv_name = "conanenvpython"

    def __init__(self, conanfile):
        super(VirtualEnvPythonGenerator, self).__init__(conanfile)
        ppath = conanfile.env.get("PYTHONPATH")
        if ppath:
            self.env.update({"PYTHONPATH": [ppath, ] if not isinstance(ppath, list) else ppath})


