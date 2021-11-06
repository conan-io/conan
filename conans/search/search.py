import os
import re
from collections import OrderedDict
from fnmatch import translate

from conans.errors import ConanException
from conans.model.info import ConanInfo
from conans.model.recipe_ref import RecipeReference
from conans.model.ref import ConanFileReference
from conans.paths import CONANINFO
from conans.search.query_parse import evaluate_postfix, infix_to_postfix
from conans.util.files import load
from conans.util.log import logger


def filter_packages(query, package_infos):
    if query is None:
        return package_infos
    try:
        if "!" in query:
            raise ConanException("'!' character is not allowed")
        if " not " in query or query.startswith("not "):
            raise ConanException("'not' operator is not allowed")
        postfix = infix_to_postfix(query) if query else []
        result = OrderedDict()
        for package_id, info in package_infos.items():
            if _evaluate_postfix_with_info(postfix, info):
                # TODO: cache2.0 maybe it would be better to make the key the full reference
                #  but the remote will return a dict with the pkgid as the key so maintain this
                result[package_id] = info
        return result
    except Exception as exc:
        raise ConanException("Invalid package query: %s. %s" % (query, exc))


def _evaluate_postfix_with_info(postfix, conan_vars_info):

    # Evaluate conaninfo with the expression

    def evaluate_info(expression):
        """Receives an expression like compiler.version="12"
        Uses conan_vars_info in the closure to evaluate it"""
        name, value = expression.split("=", 1)
        value = value.replace("\"", "")
        return _evaluate(name, value, conan_vars_info)

    return evaluate_postfix(postfix, evaluate_info)


def _evaluate(prop_name, prop_value, conan_vars_info):
    """
    Evaluates a single prop_name, prop_value like "os", "Windows" against
    conan_vars_info.serialize_min()
    """

    def compatible_prop(setting_value, _prop_value):
        return (_prop_value == setting_value) or (_prop_value == "None" and setting_value is None)

    info_settings = conan_vars_info.get("settings", [])
    info_options = conan_vars_info.get("options", [])
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
        if isinstance(pattern, (ConanFileReference, RecipeReference)):
            pattern = repr(pattern)
        pattern = translate(pattern)
        pattern = re.compile(pattern, re.IGNORECASE) if ignorecase else re.compile(pattern)

    refs = cache.all_refs()
    refs.extend(cache.editable_packages.edited_refs.keys())
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


# TODO: cache2.0 for the moment we are passing here a list of layouts to later get the conaninfos
#  we should refactor this to something better
def search_packages(packages_layouts, packages_query):
    """ Return a dict like this:

            {package_ID: {name: "OpenCV",
                           version: "2.14",
                           settings: {os: Windows}}}
    param package_layout: Layout for the given reference
    """

    infos = _get_local_infos_min(packages_layouts)
    return filter_packages(packages_query, infos)


def _get_local_infos_min(packages_layouts):
    result = OrderedDict()

    for pkg_layout in packages_layouts:
        # Read conaninfo
        info_path = os.path.join(pkg_layout.package(), CONANINFO)
        if not os.path.exists(info_path):
            logger.error("There is no ConanInfo: %s" % str(info_path))
            continue
        conan_info_content = load(info_path)

        info = ConanInfo.loads(conan_info_content)
        conan_vars_info = info.serialize_min()
        # TODO: cache2.0 use the full ref or package rev as key
        # FIXME: cache2.0 there will be several prevs with same package id
        result[pkg_layout.reference.package_id] = conan_vars_info

    return result
