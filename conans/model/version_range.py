from collections import namedtuple

from conans.errors import ConanException
from conans.model.recipe_ref import Version


_Condition = namedtuple("_Condition", ["operator", "version"])


def _parse_expression(expression):
    operator = expression[0]
    if operator not in (">", "<", "^", "~"):
        operator = "="
        index = 0
    else:
        index = 1
    if operator in (">", "<"):
        if expression[1] == "=":
            operator += "="
            index = 2
    version = expression[index:]
    if operator == "~":  # tilde minor
        v = Version(version)
        return [_Condition(">=", v), _Condition("<", v.bump(1))]
    elif operator == "^":  # caret major
        v = Version(version)

        def first_non_zero(main):
            for i, m in enumerate(main):
                if m != 0:
                    return i
            return len(main)

        initial_index = first_non_zero(v.main)
        return [_Condition(">=", v), _Condition("<", v.bump(initial_index))]
    else:
        return [_Condition(operator, Version(version))]


class VersionRange:
    def __init__(self, expression):
        self._expression = expression
        expressions = expression.split()
        self.conditions = []
        for expression in expressions:
            self.conditions.extend(_parse_expression(expression))

    def __contains__(self, version):
        assert isinstance(version, Version), type(version)
        for condition in self.conditions:
            if condition.operator == ">":
                if not version > condition.version:
                    return False
            elif condition.operator == "<":
                if not version < condition.version:
                    return False
            elif condition.operator == ">=":
                if not version >= condition.version:
                    return False
            elif condition.operator == "<=":
                if not version <= condition.version:
                    return False
            elif condition.operator == "=":
                if not version == condition.version:
                    return False
        return True
