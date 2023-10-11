from collections import namedtuple
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
            if self.operator == ">=":
                return False
            elif self.operator == "<":
                return True

        return False


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
        lower_limits = [c for c in self.condition_sets[0].conditions if c.operator in (">", ">=")]
        lower_limits += [c for c in other.condition_sets[0].conditions if c.operator in (">", ">=")]
        print(lower_limits)
        lower_limit = sorted(lower_limits, reverse=True)[0]
        print(lower_limit)

        upper_limits = [c for c in self.condition_sets[0].conditions if c.operator in ("<", "<=")]
        upper_limits += [c for c in other.condition_sets[0].conditions if c.operator in ("<", "<=")]
        print(upper_limits)
        upper_limit = sorted(upper_limits)[0]
        print(upper_limit)

        if lower_limit >= upper_limit:
            return None

        result = VersionRange(f"[{lower_limit.operator}{lower_limit.version} "
                              f"{upper_limit.operator}{upper_limit.version}]")
        print(str(result))
        # result.condition_sets = self.condition_sets + other.condition_sets
        return result

    def version(self):
        return Version(self._expression)

    def invalid(self):
        pass

