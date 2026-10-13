import ast
import os


def _always_true(test):
    """ assert "text" or assert "text {}".format(...), which never fail, were probably meant to
    be assert "text" in client.out
    """
    if isinstance(test, ast.Constant):
        return isinstance(test.value, str) and test.value != ""
    if isinstance(test, ast.JoinedStr):
        return True
    return (isinstance(test, ast.Call) and isinstance(test.func, ast.Attribute)
            and isinstance(test.func.value, ast.Constant) and isinstance(test.func.value.value, str))


def test_no_always_true_asserts():
    test_folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    errors = []
    for root, _, files in os.walk(test_folder):
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            with open(path, encoding="utf-8") as fd:
                tree = ast.parse(fd.read(), filename=path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assert) and _always_true(node.test):
                    errors.append(f"{os.path.relpath(path, test_folder)}:{node.lineno}")
    assert not errors, "These assertions can never fail:\n" + "\n".join(errors)
