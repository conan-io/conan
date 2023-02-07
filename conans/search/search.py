import os
import re
from collections import OrderedDict
from fnmatch import translate
from typing import Dict

from conan.api.output import ConanOutput
from conans.errors import ConanException
from conans.model.info import load_binary_info
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.paths import CONANINFO
from conans.search.query_parse import evaluate_postfix, infix_to_postfix
from conans.util.files import load


def filter_packages(query, results: Dict[PkgReference, dict]):
    if query is None:
        return results
    try:
        if "!" in query:
            raise ConanException("'!' character is not allowed")
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
    info_settings = binary_info.get("settings")
    info_options = binary_info.get("options")
    properties = ["os", "compiler", "arch", "build_type"]

    def starts_with_common_settings(_prop_name):
        return any(_prop_name.startswith(setting + '.') for setting in properties)

    if prop_name in properties or starts_with_common_settings(prop_name):
        return compatible_prop(info_settings.get(prop_name, None), prop_value)
    else:
        return compatible_prop(info_options.get(prop_name, None), prop_value)


def search_recipes(cache, pattern=None, ignorecase=True):
    # Conan references in main storage
    if pattern:
        if isinstance(pattern, RecipeReference):
            pattern = repr(pattern)
        pattern = translate(pattern)
        pattern = re.compile(pattern, re.IGNORECASE) if ignorecase else re.compile(pattern)

    refs = cache.all_refs()
    if pattern:
        _refs = []
        for r in refs:
            match_ref = str(r) if not r.revision else repr(r)
            if _partial_match(pattern, match_ref):
                _refs.append(r)
        refs = _refs
    return refs


def _partial_match(pattern, reference):
    """
    Finds if pattern matches any of partial sums of tokens of conan reference
    """
    tokens = reference.replace('/', ' / ').replace('@', ' @ ').replace('#', ' # ').split()

    def partial_sums(iterable):
        partial = ''
        for i in iterable:
            partial += i
            yield partial

    return any(map(pattern.match, list(partial_sums(tokens))))


def get_cache_packages_binary_info(cache, prefs) -> Dict[PkgReference, dict]:
    """
    param package_layout: Layout for the given reference
    """

    result = OrderedDict()

    package_layouts = []
    for pref in prefs:
        latest_prev = cache.get_latest_package_reference(pref)
        package_layouts.append(cache.pkg_layout(latest_prev))

    for pkg_layout in package_layouts:
        # Read conaninfo
        info_path = os.path.join(pkg_layout.package(), CONANINFO)
        if not os.path.exists(info_path):
            ConanOutput().error("There is no conaninfo.txt: %s" % str(info_path))
            continue
        conan_info_content = load(info_path)

        info = load_binary_info(conan_info_content)
        pref = pkg_layout.reference
        # The key shoudln't have the latest package revision, we are asking for package configs
        pref.revision = None
        result[pkg_layout.reference] = info

    return result
