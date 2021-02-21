

class ConanFileInterface:
    """ this is just a protective wrapper to give consumers
    a limited view of conanfile dependencies, "read" only,
    and only to some attributes, not methods
    """

    def __init__(self, conanfile):
        self._conanfile = conanfile

    @property
    def buildenv_info(self):
        return self._conanfile.buildenv_info

    @property
    def runenv_info(self):
        return self._conanfile.runenv_info

    @property
    def cpp_info(self):
        return self._conanfile.cpp_info
