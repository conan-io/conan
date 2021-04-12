

class ConanFileInterface:
    """ this is just a protective wrapper to give consumers
    a limited view of conanfile dependencies, "read" only,
    and only to some attributes, not methods
    """
    def __str__(self):
        return str(self._conanfile)

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def __eq__(self, other):
        """
        The conanfile is a different entity per node, and conanfile equality is identity
        :type other: ConanFileInterface
        """
        return self._conanfile == other._conanfile

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def name(self):
        return self._conanfile.name

    @property
    def buildenv_info(self):
        return self._conanfile.buildenv_info

    @property
    def runenv_info(self):
        return self._conanfile.runenv_info

    @property
    def cpp_info(self):
        return self._conanfile.cpp_info

    @property
    def settings(self):
        return self._conanfile.settings

    @property
    def context(self):
        return self._conanfile.context

    @property
    def dependencies(self):
        return self._conanfile.dependencies
