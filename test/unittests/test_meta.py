""" Meta tests: they do not test Conan, they check the test files themselves for patterns that
must not be used
"""
import ast
import io
import os
import tokenize

import pytest

_TEST_FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _test_files():
    """ yields (path relative to the test folder, source) for every .py file of the tests """
    for root, _, files in os.walk(_TEST_FOLDER):
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            with open(path, encoding="utf-8") as fd:
                yield os.path.relpath(path, _TEST_FOLDER), fd.read()


class TestNoAlwaysTrueAsserts:
    """ assert "text" or assert "text {}".format(...) """

    @staticmethod
    def _always_true(test):
        """ assert "text" or assert "text {}".format(...), which never fail, were probably meant
        to be assert "text" in client.out
        """
        if isinstance(test, ast.Constant):
            return isinstance(test.value, str) and test.value != ""
        if isinstance(test, ast.JoinedStr):
            return True
        return (isinstance(test, ast.Call) and isinstance(test.func, ast.Attribute)
                and isinstance(test.func.value, ast.Constant)
                and isinstance(test.func.value.value, str))

    def test_no_always_true_asserts(self):
        errors = []
        for path, source in _test_files():
            for node in ast.walk(ast.parse(source, filename=path)):
                if isinstance(node, ast.Assert) and self._always_true(node.test):
                    errors.append(f"{path}:{node.lineno}")
        assert not errors, "These assertions can never fail:\n" + "\n".join(errors)


class TestNoParenthesizedContextManagers:
    """ with (a as x, b as y): """

    _SKIP = {tokenize.NL, tokenize.COMMENT, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT}

    @classmethod
    def _parenthesized_with_lines(cls, source):
        """ Lines of the "with (a as x, b as y):" statements, which are a syntax error in Python
        3.8 (and "with (a, b):" is a tuple there, not 2 context managers). "with (a):" and
        "with (a).b() as c:" are fine in every version and are not reported
        """
        tokens = [t for t in tokenize.generate_tokens(io.StringIO(source).readline)
                  if t.type not in cls._SKIP]
        lines = []
        for i, tok in enumerate(tokens):
            if tok.type != tokenize.NAME or tok.string != "with":
                continue
            if i + 1 >= len(tokens) or tokens[i + 1].string != "(":
                continue
            depth, top_level_separator = 0, False
            for j in range(i + 1, len(tokens)):
                t = tokens[j]
                if t.type == tokenize.OP and t.string in "([{":
                    depth += 1
                elif t.type == tokenize.OP and t.string in ")]}":
                    depth -= 1
                    if depth == 0:
                        closes_with_items = j + 1 < len(tokens) and tokens[j + 1].string == ":"
                        if closes_with_items and top_level_separator:
                            lines.append(tok.start[0])
                        break
                elif depth == 1 and (t.string == ","
                                     or (t.type == tokenize.NAME and t.string == "as")):
                    top_level_separator = True
        return lines

    @pytest.mark.parametrize("source, expected", [
        ("with (open('a') as a, open('b') as b):\n    pass\n", [1]),
        ("with (\n    open('a') as a,\n    open('b') as b,\n):\n    pass\n", [1]),
        ("with (open('a'), open('b')):\n    pass\n", [1]),
        ("with (open('a') as a):\n    pass\n", [1]),
        ("async def f():\n    async with (a as x, b as y):\n        pass\n", [2]),
        ("with open('a') as a, open('b') as b:\n    pass\n", []),
        ("with (open('a')):\n    pass\n", []),
        ("with (a).b() as c, d:\n    pass\n", []),
        ("with f(a, b) as c:\n    pass\n", []),
        ("with (a if x else b) as c:\n    pass\n", []),
        ("with (yield):\n    pass\n", []),
        ("with \\\n    open('a') as a, \\\n    open('b') as b:\n    pass\n", []),
    ])
    def test_detector(self, source, expected):
        assert self._parenthesized_with_lines(source) == expected

    def test_no_parenthesized_context_managers(self):
        """ Parenthesized context managers are only valid from Python 3.9/3.10, the tests must
        keep working in Python 3.8, use backslashes or nested "with" statements instead
        """
        errors = [f"{path}:{lineno}" for path, source in _test_files()
                  for lineno in self._parenthesized_with_lines(source)]
        assert not errors, "Parenthesized context managers are not supported in Python 3.8:\n" \
                           + "\n".join(errors)
