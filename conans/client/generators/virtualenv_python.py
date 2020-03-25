from conans.client.generators.virtualrunenv import VirtualRunEnvGenerator
from conans.util.conan_v2_mode import conan_v2_behavior


class VirtualEnvPythonGenerator(VirtualRunEnvGenerator):

    suffix = "_run_python"
    venv_name = "conanenvpython"

    def __init__(self, conanfile):
        conan_v2_behavior("'virtualenv_python' generator is deprecated")
        super(VirtualEnvPythonGenerator, self).__init__(conanfile)
        ppath = conanfile.env.get("PYTHONPATH")
        if ppath:
            self.env.update({"PYTHONPATH": [ppath, ] if not isinstance(ppath, list) else ppath})
