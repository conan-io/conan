class CMakeToolchainBase(object):
    filename = "conan_toolchain.cmake"

    def __init__(self, conanfile, *args, **kwargs):
        self._conanfile = conanfile
