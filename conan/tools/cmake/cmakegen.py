from conan.tools.cmake import CMakeDeps, CMakeToolchain
from conan.tools.env import VirtualEnv


class CMakeGen(object):  # Needed for Py2
    def __init__(self, conanfile):
        self.toolchain = CMakeToolchain(conanfile)
        self.deps = CMakeDeps(conanfile)
        self.env = VirtualEnv(conanfile)

    def generate(self):
        self.toolchain.generate()
        self.deps.generate()
        self.env.generate()

    def _output_path(self, value):
        self.toolchain.output_path = value
        self.deps.output_path = value
        self.env.output_path = value

    output_path = property(fset=_output_path)  # now value has only a setter
