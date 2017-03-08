import os
from conans.model.ref import ConanFileReference

class ConanGrapher(object):
    def __init__(self, project_reference, deps_graph):
        self._deps_graph = deps_graph
        self._project_reference = project_reference

    def graph(self, output_file):
        graph_lines = []

        graph_lines.append('digraph {\n')

        for node in self._deps_graph.nodes:
            ref = node.conan_ref

            if ref is None:
                ref = self._project_reference

            depends = self._deps_graph.neighbors(node)

            if depends:
                graph_lines.append('    "%s" -> {' % str(ref))

                for i, dep in enumerate(depends):
                    graph_lines.append('"%s"' % str(dep.conan_ref))

                    if i == len(depends) - 1:
                        graph_lines.append('}\n')
                    else:
                        graph_lines.append(' ')

        graph_lines.append('}\n')

        graph_lines_string = ''.join(graph_lines)

        self.graph_file(graph_lines_string, output_file)

    def graph_file(self, graph, output_filename):
        output_file = os.path.join(os.getcwd(), output_filename)

        with open(output_file, 'w') as f:
            f.write(graph)
