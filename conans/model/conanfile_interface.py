from conans.client.graph.graph import CONTEXT_BUILD


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

    def __hash__(self):
        return hash(self._conanfile)

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def package_folder(self):
        return self._conanfile.package_folder

    @property
    def ref(self):
        return self._conanfile.ref

    @property
    def pref(self):
        return self._conanfile.pref

    @property
    def buildenv_info(self):
        return self._conanfile.buildenv_info

    @property
    def runenv_info(self):
        return self._conanfile.runenv_info

    @property
    def cpp_info(self):
        return self._conanfile.new_cpp_info

    @property
    def settings(self):
        return self._conanfile.settings

    @property
    def settings_build(self):
        return self._conanfile.settings_build

    @property
    def options(self):
        return self._conanfile.options

    @property
    def context(self):
        return self._conanfile.context

    @property
    def conf_info(self):
        return self._conanfile.conf_info

    @property
    def dependencies(self):
        return self._conanfile.dependencies

    @property
    def is_build_context(self):
        return self._conanfile.context == CONTEXT_BUILD
