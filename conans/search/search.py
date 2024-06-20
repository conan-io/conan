import re
from collections import OrderedDict
from fnmatch import translate
from typing import Dict

from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.search.query_parse import evaluate_postfix, infix_to_postfix


def filter_packages(query, results: Dict[PkgReference, dict]):
    if query is None:
        return results
    try:
        if "!" in query:
            raise ConanException("'!' character is not allowed")
        if "~" in query:
            raise ConanException("'~' character is not allowed")
        if " not " in query or query.startswith("not "):
            raise ConanException("'not' operator is not allowed")
        postfix = infix_to_postfix(query) if query else []
        result = OrderedDict()
        for pref, data in results.items():
            if _evaluate_postfix_with_info(postfix, data):
                result[pref] = data
        return result
    except Exception as exc:
        raise ConanException("Invalid package query: %s. %s" % (query, exc))


def _evaluate_postfix_with_info(postfix, binary_info):

    # Evaluate conaninfo with the expression

    def evaluate_info(expression):
        """Receives an expression like compiler.version="12"
        Uses conan_vars_info in the closure to evaluate it"""
        name, value = expression.split("=", 1)
        value = value.replace("\"", "")
        return _evaluate(name, value, binary_info)

    return evaluate_postfix(postfix, evaluate_info)


def _evaluate(prop_name, prop_value, binary_info):
    """
    Evaluates a single prop_name, prop_value like "os", "Windows" against
    conan_vars_info.serialize_min()
    """

    def compatible_prop(setting_value, _prop_value):
        return (_prop_value == setting_value) or (_prop_value == "None" and setting_value is None)

    # TODO: Necessary to generalize this query evaluation to include all possible fields
    info_settings = binary_info.get("settings", {})
    info_options = binary_info.get("options", {})

    if not prop_name.startswith("options."):
        return compatible_prop(info_settings.get(prop_name), prop_value)
    else:
        prop_name = prop_name[len("options."):]
        return compatible_prop(info_options.get(prop_name), prop_value)




def _partial_match(pattern, reference):
    """
    Finds if pattern matches any of partial sums of tokens of conan reference
    """
    tokens = reference.replace('/', ' / ').replace('@', ' @ ').replace('#', ' # ').split()
    partials = []
    partial = ''
    for t in tokens:
        partial += t
        partials.append(partial)

    return any(map(pattern.match, partials))
