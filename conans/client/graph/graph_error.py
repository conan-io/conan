from conans.errors import ConanException


class GraphError(ConanException):
    LOOP = "graph loop"
    VERSION_CONFLICT = "version conflict"
    PROVIDE_CONFLICT = "provide conflict"
    CONFIG_CONFLICT = "configuration conflict"
    MISSING_RECIPE = "missing recipe"
    RUNTIME = "runtime"

    def __init__(self, kind):
        self.kind = kind

    def __str__(self):
        # TODO: Nicer error reporting
        if self.kind == GraphError.MISSING_RECIPE:
            return f"Package '{self.require.ref}' not resolved: {self.missing_error}"
        return self.kind

    @staticmethod
    def loop(node, require, ancestor):
        result = GraphError(GraphError.LOOP)
        result.node = node
        result.require = require
        result.ancestor = ancestor
        node.error = ancestor.error = result
        return result

    @staticmethod
    def runtime(node, conflicting_node):
        result = GraphError(GraphError.RUNTIME)
        result.node = node
        result.conflicting_node = conflicting_node
        node.error = conflicting_node.error = result
        return result

    @staticmethod
    def provides(node, conflicting_node):
        result = GraphError(GraphError.PROVIDE_CONFLICT)
        result.node = node
        result.conflicting_node = conflicting_node
        node.error = conflicting_node.error = result
        return result

    @staticmethod
    def missing(node, require, missing_error):
        result = GraphError(GraphError.MISSING_RECIPE)
        result.node = node
        result.require = require
        result.missing_error = missing_error
        node.error = result
        return result

    @staticmethod
    def conflict(node, require, prev_node, prev_require, base_previous):
        result = GraphError(GraphError.VERSION_CONFLICT)
        result.node = node
        result.require = require
        result.prev_node = prev_node
        result.prev_require = prev_require
        result.base_previous = base_previous
        node.error = base_previous.error = result
        if prev_node:
            prev_node.error = result
        return result

    @staticmethod
    def conflict_config(node, require, prev_node, prev_require, base_previous,
                        option, previous_value, new_value):
        result = GraphError(GraphError.CONFIG_CONFLICT)
        result.node = node
        result.require = require
        result.prev_node = prev_node
        result.prev_require = prev_require
        result.base_previous = base_previous
        result.option = option
        result.previous_value = previous_value
        result.new_value = new_value
        node.error = base_previous.error = result
        if prev_node:
            prev_node.error = result
        return result

    def report_graph_error(self):
        # FIXME: THis is completely broken and useless
        # print("REPORTING GRAPH ERRORS")
        conflict_nodes = [n for n in self.nodes if n.conflict]
        # print("PROBLEMATIC NODES ", conflict_nodes)
        for node in conflict_nodes:  # At the moment there should be only 1 conflict at most
            conflict = node.conflict
            # print("CONFLICT ", conflict)
            if conflict[0] == GraphError.LOOP:
                loop_ref = node.ref
                parent = node.dependants[0]
                parent_ref = parent.src.ref
                msg = "Loop detected in context host: '{}' requires '{}' which "\
                      "is an ancestor too"
                msg = msg.format(parent_ref, loop_ref)
                raise ConanException(msg)
            elif conflict[0] == GraphError.VERSION_CONFLICT:
                raise ConanException(
                    "There was a version conflict building the dependency graph")
            elif conflict[0] == GraphError.PROVIDE_CONFLICT:
                raise ConanException(
                    "There was a provides conflict building the dependency graph")

        raise ConanException("Thre was an error in the graph: {}".format(self.error))
