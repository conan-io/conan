from conan.tools.cmake import CMakeDeps, CMakeToolchain
from conan.tools.env import VirtualEnv


class CMakeGen:
    def __init__(self, conanfile):
        self.toolchain = CMakeToolchain(conanfile)
        self.deps = CMakeDeps(conanfile)
        self.env = VirtualEnv(conanfile)

    def generate(self):
        self.toolchain.generate()
        self.deps.generate()
        self.env.generate()
