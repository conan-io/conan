from conans.client.graph.graph import CONTEXT_HOST
from conans.model.conanfile_interface import ConanFileInterface


class ConanFileDependencies:

    def __init__(self, node):
        self._node = node

    @property
    def build_requires(self):
        return [ConanFileInterface(edge.dst.conanfile) for edge in self._node.dependencies
                if edge.build_require]

    @property
    def requires(self):
        # public direct requires
        return [ConanFileInterface(edge.dst.conanfile) for edge in self._node.dependencies
                if not edge.build_require and not edge.private]

    @property
    def direct_host_requires(self):
        return self.requires + [br for br in self.build_requires if br.context == CONTEXT_HOST]

    @property
    def host_requires(self):
        result = []
        next_requires = self.direct_host_requires
        while next_requires:
            new_requires = []
            for require in next_requires:
                if require not in new_requires and require not in result:
                    result.append(require)
                for transitive in require.dependencies.requires:
                    if transitive not in new_requires:
                        new_requires.append(transitive)
            next_requires = new_requires
        return result
