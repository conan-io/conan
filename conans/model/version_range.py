from collections import namedtuple

from conans.errors import ConanException
from conans.model.recipe_ref import Version


_Condition = namedtuple("_Condition", ["operator", "version"])


class _ConditionSet:

    def __init__(self, expression, prerelease):
        expressions = expression.split()
        self.prerelease = prerelease
        self.conditions = []
        for e in expressions:
            e = e.strip()
            if e[-1] == "-":  # Include pre-releases
                e = e[:-1]
                self.prerelease = True
            self.conditions.extend(self._parse_expression(e))

    @staticmethod
    def _parse_expression(expression):
        if expression == "" or expression == "*":
            return [_Condition(">=", Version("0.0.0"))]

        operator = expression[0]
        if operator not in (">", "<", "^", "~", "="):
            operator = "="
            index = 0
        else:
            index = 1
        if operator in (">", "<"):
            if expression[1] == "=":
                operator += "="
                index = 2
        version = expression[index:]
        if version == "":
            raise ConanException(f"Error parsing version range {expression}")
        if operator == "~":  # tilde minor
            v = Version(version)
            index = 1 if len(v.main) > 1 else 0
            return [_Condition(">=", v), _Condition("<", v.upper_bound(index))]
        elif operator == "^":  # caret major
            v = Version(version)

            def first_non_zero(main):
                for i, m in enumerate(main):
                    if m != 0:
                        return i
                return len(main)

            initial_index = first_non_zero(v.main)
            return [_Condition(">=", v), _Condition("<", v.upper_bound(initial_index))]
        else:
            return [_Condition(operator, Version(version))]

    def valid(self, version):
        if version.pre:
            if not self.prerelease:
                return False
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


class VersionRange:
    def __init__(self, expression):
        self._expression = expression
        tokens = expression.split(",")
        prereleases = None
        for t in tokens[1:]:
            if "include_prerelease" in t:
                prereleases = True
                break
        version_expr = tokens[0]
        self.condition_sets = []
        for alternative in version_expr.split("||"):
            self.condition_sets.append(_ConditionSet(alternative, prereleases))

    def __str__(self):
        return self._expression

    def __contains__(self, version):
        assert isinstance(version, Version), type(version)
        for condition_set in self.condition_sets:
            if condition_set.valid(version):
                return True
        return False
