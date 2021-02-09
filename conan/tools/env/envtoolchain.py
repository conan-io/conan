from conan.tools.env import Environment


class EnvToolchain:

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def env(self):
        # Visit all dependencies
        env = Environment()
        for node in self._conanfile.deps:
            env = env.compose(node.env)
        return env

    def generate(self):
        # Visit all dependencies
        env = self.env()
        env.save_bat("envtoolchain.bat")
        env.save_sh("envtoolchain.sh")
