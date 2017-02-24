import os
from conans.model.ref import ConanFileReference

class ConanGrapher(object):
    def __init__(self, project_reference, deps_graph):
        self._deps_graph = deps_graph
        self._project_reference = project_reference

    def graph(self):
        output_file = os.path.join(os.getcwd(), "graph.dot")
        f = open(output_file, 'w')

        f.write('digraph {\n')

        for node in self._deps_graph.nodes:
            ref = node.conan_ref

            if ref is None:
                ref = self._project_reference

            depends = self._deps_graph.neighbors(node)

            if depends:
                f.write('    "%s" -> {' % str(ref))

                for i, dep in enumerate(depends):
                    f.write('"%s"' % str(dep.conan_ref))

                    if i == len(depends) - 1:
                        f.write('}\n')
                    else:
                        f.write(' ')

        f.write('}\n');

        f.close()
