

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
    def version(self):
        return self._conanfile.version

    @property
    def user(self):
        return self._conanfile.user

    @property
    def channel(self):
        return self._conanfile.channel

    @property
    def recipe_revision(self):
        return self._conanfile.recipe_revision

    @property
    def ref(self):
        return self._conanfile.ref

    @property
    def package_id(self):
        return self._conanfile.package_id

    @property
    def package_revision(self):
        return self._conanfile.package_revision

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
