
class Toolchain(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile


class CMakeToolchain(Toolchain):
    def __init__(self, conanfile):
        super(CMakeToolchain, self).__init__(conanfile)

