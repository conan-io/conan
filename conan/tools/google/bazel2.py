import platform

from conan.tools.build import load_toolchain_args


class Bazel(object):
    def __init__(self, conanfile, namespace=None):
        self._conanfile = conanfile

    def configure(self, args=None):
        pass

    def build(self, args=None):
        pass

    def install(self):
        pass

    def test(self):
        pass
