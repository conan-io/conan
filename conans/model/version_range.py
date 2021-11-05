import re

from conans.model.recipe_ref import Version


class _Condition:
    def __init__(self, operator, version):
        self.operator = operator
        self.version = version

    def __str__(self):
        return f"{self.operator},{self.version}"


def _parse_expression(expression):
    operator_regex = re.compile("(=|>|<|>=|<|<=)")
    tokens = operator_regex.split(expression, 1)
    tokens = tokens[1:]
    operator, version = tokens
    return [_Condition(operator, Version(version))]


class VersionRange:
    def __init__(self, expression):
        self._expression = expression
        expressions = expression.split()
        self.conditions = []
        for expression in expressions:
            self.conditions.extend(_parse_expression(expression))

    def __contains__(self, version):
        assert isinstance(version, Version)
        for condition in self.conditions:
            if condition.operator == ">":
                if not version > condition.version:
                    return False
            elif condition.operator == "<":
                if not version < condition.version:
                    return False
        return True
