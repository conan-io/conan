from conans.errors import ConanException


class GraphError(ConanException):
    # TODO: refactor into multiple classes, do not do type by attribute "kind"
    LOOP = "graph loop"
    VERSION_CONFLICT = "version conflict"
    PROVIDE_CONFLICT = "provide conflict"
    MISSING_RECIPE = "missing recipe"
    RUNTIME = "runtime"

    def __init__(self, kind):
        self.kind = kind

    def __str__(self):
        # TODO: Nicer error reporting
        if self.kind == GraphError.MISSING_RECIPE:
            return f"Package '{self.require.ref}' not resolved: {self.missing_error}"
        elif self.kind == GraphError.VERSION_CONFLICT:
            return f"Version conflict: {self.node.ref}->{self.require.ref}, "\
                   f"{self.base_previous.ref}->{self.prev_require.ref}."
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
