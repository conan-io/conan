from conans.errors import ConanException


class GraphError(ConanException):
    pass


class GraphConflictError(GraphError):

    def __init__(self, node, require, prev_node, prev_require, base_previous):
        self.node = node
        self.require = require
        self.prev_node = prev_node
        self.prev_require = prev_require
        self.base_previous = base_previous

    def __str__(self):
        return f"Version conflict: {self.node.ref}->{self.require.ref}, "\
               f"{self.base_previous.ref}->{self.prev_require.ref}."


class GraphLoopError(GraphError):

    def __init__(self, node, require, ancestor):
        self.node = node
        self.require = require
        self.ancestor = ancestor

    def __str__(self):
        return "There is a cycle/loop in the graph:\n"\
               f"    Initial ancestor: {self.ancestor}\n" \
               f"    Require: {self.require.ref}\n" \
               f"    Dependency: {self.node}"


class GraphMissingError(GraphError):

    def __init__(self, node, require, missing_error):
        self.node = node
        self.require = require
        self.missing_error = missing_error

    def __str__(self):
        return f"Package '{self.require.ref}' not resolved: {self.missing_error}."


class GraphProvidesError(GraphError):

    def __init__(self, node, conflicting_node):
        self.node = node
        self.conflicting_node = conflicting_node
        node.error = conflicting_node.error

    def __str__(self):
        return f"Provide Conflict: Both '{self.node.ref}' and '{self.conflicting_node.ref}' " \
               f"provide '{self.node.conanfile.provides}'."


class GraphRuntimeError(GraphError):

    def __init__(self, node, conflicting_node):
        self.node = node
        self.conflicting_node = conflicting_node

    def __str__(self):
        return f"Runtime Error: Could not process '{self.node.ref}' with " \
               f"'{self.conflicting_node.ref}'."
