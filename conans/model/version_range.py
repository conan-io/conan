from functools import total_ordering
from typing import Optional

from conans.errors import ConanException
from conans.model.recipe_ref import Version


@total_ordering
class _Condition:
    def __init__(self, operator, version):
        self.operator = operator
        self.version = version

    def __str__(self):
        return f"{self.operator}{self.version}"

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return hash((self.operator, self.version))

    def __lt__(self, other):
        if self.version < other.version:
            return True
        elif self.version == other.version:
            if "<" in self.operator:
                assert "<" in other.operator  # Only ordering possible
                return other.operator == "<="
            else:
                if ">" in other.operator:
                    return other.operator == ">"
                else:  # valid range check lower against upper
                    return self.operator == ">=" and other.operator == "<="
        return False

    def __eq__(self, other):
        return (self.version == other.version and
                self.operator == other.operator)


class _ConditionSet:

    def __init__(self, expression, prerelease):
        expressions = expression.split()
        self.prerelease = prerelease
        self.conditions = []
        for e in expressions:
            e = e.strip()
            self.conditions.extend(self._parse_expression(e))

    @staticmethod
    def _parse_expression(expression):
        if expression in ("", "*"):
            return [_Condition(">=", Version("0.0.0"))]
        elif len(expression) == 1:
            raise ConanException(f'Error parsing version range "{expression}"')

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
            raise ConanException(f'Error parsing version range "{expression}"')
        if operator == "~":  # tilde minor
            if "-" not in version:
                version += "-"
            v = Version(version)
            index = 1 if len(v.main) > 1 else 0
            return [_Condition(">=", v), _Condition("<", v.upper_bound(index))]
        elif operator == "^":  # caret major
            if "-" not in version:
                version += "-"
            v = Version(version)

            def first_non_zero(main):
                for i, m in enumerate(main):
                    if m != 0:
                        return i
                return len(main)

            initial_index = first_non_zero(v.main)
            return [_Condition(">=", v), _Condition("<", v.upper_bound(initial_index))]
        else:
            if (operator == ">=" or operator == "<") and "-" not in version:
                version += "-"
            return [_Condition(operator, Version(version))]

    def _valid(self, version, conf_resolve_prepreleases):
        if version.pre:
            # Follow the expression desires only if core.version_ranges:resolve_prereleases is None,
            # else force to the conf's value
            if conf_resolve_prepreleases is None:
                if not self.prerelease:
                    return False
            elif conf_resolve_prepreleases is False:
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
        prereleases = False
        for t in tokens[1:]:
            if "include_prerelease" in t:
                if "include_prerelease=" in t:
                    from conan.api.output import ConanOutput
                    ConanOutput().warning(
                        f'include_prerelease version range option in "{expression}" does not take an attribute, '
                        'its presence unconditionally enables prereleases')
                prereleases = True
                break
            else:
                t = t.strip()
                if len(t) > 0 and t[0].isalpha():
                    from conan.api.output import ConanOutput
                    ConanOutput().warning(f'Unrecognized version range option "{t}" in "{expression}"')
                else:
                    raise ConanException(f'"{t}" in version range "{expression}" is not a valid option')
        version_expr = tokens[0]
        self.condition_sets = []
        for alternative in version_expr.split("||"):
            self.condition_sets.append(_ConditionSet(alternative, prereleases))

    def __str__(self):
        return self._expression

    def contains(self, version: Version, resolve_prerelease: Optional[bool]):
        """
        Whether <version> is inside the version range

        :param version: Version to check against
        :param resolve_prerelease: If ``True``, ensure prereleases can be resolved in this range
        If ``False``, prerelases can NOT be resolved in this range
        If ``None``, prereleases are resolved only if this version range expression says so
        :return: Whether the version is inside the range
        """
        assert isinstance(version, Version), type(version)
        for condition_set in self.condition_sets:
            if condition_set._valid(version, resolve_prerelease):
                return True
        return False

    def intersection(self, other):
        # TODO: assumes just 1 condition set
        if len(self.condition_sets) != 1 or len(other.condition_sets) != 1:
            return

        conditions = []
        lower_limits = [c for c in self.condition_sets[0].conditions if ">" in c.operator]
        lower_limits.extend(c for c in other.condition_sets[0].conditions if ">" in c.operator)
        lower_limit = None
        if lower_limits:
            lower_limit = sorted(lower_limits, reverse=True)[0]
            conditions.append(lower_limit)

        upper_limits = [c for c in self.condition_sets[0].conditions if "<" in c.operator]
        upper_limits.extend(c for c in other.condition_sets[0].conditions if "<" in c.operator)
        upper_limit = None
        if upper_limits:
            upper_limit = sorted(upper_limits)[0]
            conditions.append(upper_limit)

        if lower_limit and upper_limit and lower_limit > upper_limit:
            return None

        result = VersionRange(f"{' '.join(str(c) for c in conditions)}")
        # TODO: Direct definition of conditions not reparsing
        # result.condition_sets = self.condition_sets + other.condition_sets
        return result

    def version(self):
        return Version(f"[{self._expression}]")
