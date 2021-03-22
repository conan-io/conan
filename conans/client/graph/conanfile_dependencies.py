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
