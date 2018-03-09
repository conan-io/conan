import astroid
from pylint.interfaces import IAstroidChecker
from pylint.checkers import BaseChecker
from pylint.checkers import utils


class ConanChecker(BaseChecker):
    __implements__ = (IAstroidChecker,)
    name = 'conan'

    msgs = {
        'W0001': ('"%s" is deprecated since Conan v%s and will be removed in v%s. %s',
                  'conan-deprecated',
                  'Code deprecated in Conan'),
    }

    @utils.check_messages('conan-deprecated')
    def visit_call(self, node):
        """Visit a Call node."""
        try:
            for inferred in node.func.infer():
                if inferred is astroid.Uninferable:
                    continue
                self._check_deprecated_method(node, inferred)
        except astroid.InferenceError:
            return

    def _check_deprecated_method(self, node, inferred):

        if isinstance(node.func, astroid.Attribute):
            func_name = node.func.attrname
        elif isinstance(node.func, astroid.Name):
            func_name = node.func.name
        else:
            # Not interested in other nodes.
            return

        # Reject nodes which aren't of interest to us.
        acceptable_nodes = (astroid.BoundMethod,
                            astroid.UnboundMethod,
                            astroid.FunctionDef)
        if not isinstance(inferred, acceptable_nodes):
            return

        if not inferred.decorators:
            return
        else:
            for decorator in inferred.decorators.nodes:
                if isinstance(decorator, astroid.node_classes.Call):
                    if decorator.func.attrname == "deprecated":
                        deprecated_in = ""
                        removed_in = ""
                        details = ""
                        for arg in decorator.func.parent.keywords:
                            if arg.arg == "deprecated_in":
                                deprecated_in = arg.value.value
                            elif arg.arg == "removed_in":
                                removed_in = arg.value.value
                            elif arg.arg == "details":
                                details = arg.value.value

                        self.add_message('conan-deprecated', node=node, args=(func_name, deprecated_in, removed_in,
                                                                              details))
        return

def register(linter):
    """required method to auto register this checker """
    linter.register_checker(ConanChecker(linter))
