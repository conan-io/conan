from conans.client.graph.graph import CONTEXT_HOST, CONTEXT_BUILD
from conans.errors import ConanException
from conans.model.conanfile_interface import ConanFileInterface


class DependencyOrderedSet:
    """ class to give a ["mydep"] access to dependencies, because recipes many times just
    want to access by dependency name, like:
    self.dependencies.requires["openssl"].version
    self.dependencies.build_requires["cmake"].ref
    """
    def __init__(self, deps=None):
        self._deps = deps or []

    def __iter__(self):
        return iter(self._deps)

    def __next__(self):
        return next(self._deps)

    def __getitem__(self, name):
        result = [d for d in self._deps if d.ref.name == name]
        if len(result) > 1:
            raise ConanException("There is more than one dependency")
        if len(result) == 0:
            raise ConanException("No dependency found")
        return result[0]

    def __add__(self, other):
        return DependencyOrderedSet(self._deps + other._deps)


class ConanFileDependencies:

    def __init__(self, node):
        self._node = node

    @property
    def build_requires(self):
        """
        :return: list of immediate direct build_requires
        """
        return DependencyOrderedSet([ConanFileInterface(edge.dst.conanfile)
                                     for edge in self._node.dependencies if edge.build_require])

    @property
    def build_requires_build_context(self):
        """
        :return: list of immediate direct build_requires, on build context.
        FIXME: Why this method? To overcome the legacy use case without 2 profiles where everthing
               is host, otherwise we can receive the same build require twice, one in
               .transitive_host_requires and one in .build_requires
        """
        return DependencyOrderedSet([ConanFileInterface(edge.dst.conanfile)
                                     for edge in self._node.dependencies if edge.build_require and
                                     edge.dst.context == CONTEXT_BUILD])

    @property
    def requires(self):
        """
        :return: list of immediate direct requires, not included build or private ones
        """
        return DependencyOrderedSet([ConanFileInterface(edge.dst.conanfile)
                                     for edge in self._node.dependencies
                                     if not edge.build_require and not edge.private])

    @property
    def host_requires(self):
        """
        :return: list of immediate direct requires and build_requires in the host context
        """
        requires = [ConanFileInterface(edge.dst.conanfile) for edge in self._node.dependencies
                    if not edge.build_require and not edge.private]
        requires.extend([ConanFileInterface(edge.dst.conanfile)
                         for edge in self._node.dependencies
                         if edge.build_require and edge.dst.context == CONTEXT_HOST])
        return DependencyOrderedSet(requires)

    @property
    def transitive_host_requires(self):
        """
        :return: list of direct_host_requires plus all the transitive regular requires of those
        """
        result = []
        next_requires = self.host_requires
        while next_requires:
            new_requires = []
            for require in next_requires:
                if require not in new_requires and require not in result:
                    result.append(require)
                for transitive in require.dependencies.requires:
                    if transitive not in new_requires:
                        new_requires.append(transitive)
            next_requires = new_requires
        return DependencyOrderedSet(result)
