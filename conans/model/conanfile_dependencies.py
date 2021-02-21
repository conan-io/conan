from collections import OrderedDict

from conans.model.conanfile_interface import ConanFileInterface


class ConanFileDependencies:

    def __init__(self):
        self._nodes = []  # Graph algorithm guarantees not duplicated
        self._get_ordered_breadth_first_cache = None  # TODO: Replace functools Conan 2.0

    @property
    def nodes(self):
        return self._nodes

    def add(self, conanfile):
        # TODO: is it better to store the wrapped or the original one?
        self._nodes.append(conanfile)

    def _get_ordered_breadth_first(self):
        """ dummy example visitor that returns ordered breadth-first all the deps
        """
        if self._get_ordered_breadth_first_cache is None:
            result = OrderedDict()  # TODO: this is a trick to get an ordered set
            open_nodes = self._nodes
            while open_nodes:
                new_open = OrderedDict()
                for n in open_nodes:
                    for d in n.dependencies.nodes:
                        new_open[d] = None
                    result[n] = None
                open_nodes = [n for n in new_open if n not in result]
            self._get_ordered_breadth_first_cache = result
        return self._get_ordered_breadth_first_cache

    @property
    def all(self):
        return [ConanFileInterface(c) for c in self._get_ordered_breadth_first()]
