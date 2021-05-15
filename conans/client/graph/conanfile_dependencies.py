from collections import OrderedDict

from conans.model.conanfile_interface import ConanFileInterface
from conans.model.requires import UserRequirementsDict


class ConanFileDependencies:

    def __init__(self, node):
        self._node = node
        d = OrderedDict((require, ConanFileInterface(transitive.node.conanfile))
                        for require, transitive in self._node.transitive_deps.items())
        self._requires = UserRequirementsDict(d)

    @property
    def build_requires(self):
        """
        :return: list of all transitive build_requires
        """
        d = OrderedDict((require, ConanFileInterface(transitive.node.conanfile))
                        for require, transitive in self._node.transitive_deps.items()
                        if require.build)
        return UserRequirementsDict(d)

    @property
    def requires(self):
        """
        :return: list of immediate direct requires, not included build or private ones
        """
        return self._requires

    @property
    def host_requires(self):
        """
        :return: list of immediate direct requires and build_requires in the host context
        """
        d = OrderedDict((require, ConanFileInterface(transitive.node.conanfile))
                        for require, transitive in self._node.transitive_deps.items()
                        if not require.build)
        return UserRequirementsDict(d)

    @property
    def transitive_host_requires(self):
        """
        :return: list of direct_host_requires plus all the transitive regular requires of those
        """
        return self.host_requires
