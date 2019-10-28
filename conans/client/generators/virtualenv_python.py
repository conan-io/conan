from conans.client.generators.virtualrunenv import VirtualRunEnvGenerator


class VirtualEnvPythonGenerator(VirtualRunEnvGenerator):
    environment_filename = "environment_python.env"

    def __init__(self, conanfile):
        super(VirtualEnvPythonGenerator, self).__init__(conanfile)
        self.venv_name = "conanenvpython"
        ppath = conanfile.env.get("PYTHONPATH")
        if ppath:
            self.env.update({"PYTHONPATH": [ppath, ] if not isinstance(ppath, list) else ppath})

    @property
    def content(self):
        tmp = super(VirtualEnvPythonGenerator, self).content
        ret = {}
        for name, value in tmp.items():
            if name != self.environment_filename:
                tmp = name.split(".")
                ret["%s_python.%s" % (tmp[0], tmp[1])] = value
            else:
                ret[name] = value

        return ret

