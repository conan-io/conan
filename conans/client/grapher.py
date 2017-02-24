import sys
from conans.model.ref import ConanFileReference

class ConanGrapher(object):
    def __init__(self, project_reference, deps_graph):
        self._deps_graph = deps_graph
        self._project_reference = project_reference

    def graph(self, output_dir):
        for node in self._deps_graph.nodes:
            ref = node.conan_ref

            if ref is None:
                ref = self._project_reference

            depends = self._deps_graph.neighbors(node)

            if depends:
                sys.stdout.write('"%s" -> {' % str(ref))

                for i, dep in enumerate(depends):
                    sys.stdout.write('"%s/%s"' % (dep.conan_ref.name, dep.conan_ref.version))

                    if i == len(depends) - 1:
                        print '}'
                    else:
                        sys.stdout.write(' ')
