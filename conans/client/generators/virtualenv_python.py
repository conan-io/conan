from conans.client.generators.virtualenv import VirtualEnvGenerator


class VirtualEnvPythonGenerator(VirtualEnvGenerator):

    def __init__(self, conanfile):
        super(VirtualEnvPythonGenerator, self).__init__(conanfile)
        self.venv_name = "conanenvpython"
        ppath = conanfile.env.get("PYTHONPATH")
        self.env = {"PYTHONPATH": [ppath, ] if not isinstance(ppath, list) else ppath}

    @property
    def content(self):
        tmp = super(VirtualEnvPythonGenerator, self).content
        ret = {}
        for name, value in tmp.items():
            tmp = name.split(".")
            ret["%s_python.%s" % (tmp[0], tmp[1])] = value

        return ret

