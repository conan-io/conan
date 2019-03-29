import os
import re
from collections import OrderedDict
from fnmatch import translate

from conans.errors import ConanException, RecipeNotFoundException
from conans.model.info import ConanInfo
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANINFO
from conans.search.query_parse import evaluate_postfix, infix_to_postfix
from conans.util.files import list_folder_subdirs, load
from conans.util.log import logger


def filter_outdated(packages_infos, recipe_hash):
    if not recipe_hash:
        return packages_infos
    result = OrderedDict()
    for package_id, info in packages_infos.items():
        try:  # Existing package_info of old package might not have recipe_hash
            if info["recipe_hash"] != recipe_hash:
                result[package_id] = info
        except KeyError:
            pass
    return result


def filter_by_revision(metadata, packages_infos):
    ok = OrderedDict()
    recipe_revision = metadata.recipe.revision
    for package_id, info in packages_infos.items():
        try:
            rec_rev = metadata.packages[package_id].recipe_revision
            if rec_rev == recipe_revision:
                ok[package_id] = info
        except KeyError:
            pass
    return ok


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
            if evaluate_postfix_with_info(postfix, info):
                result[package_id] = info
        return result
    except Exception as exc:
        raise ConanException("Invalid package query: %s. %s" % (query, exc))


def evaluate_postfix_with_info(postfix, conan_vars_info):

    # Evaluate conaninfo with the expression

    def evaluate_info(expression):
        """Receives an expression like compiler.version="12"
        Uses conan_vars_info in the closure to evaluate it"""
        name, value = expression.split("=", 1)
        value = value.replace("\"", "")
        return evaluate(name, value, conan_vars_info)

    return evaluate_postfix(postfix, evaluate_info)


def evaluate(prop_name, prop_value, conan_vars_info):
    """
    Evaluates a single prop_name, prop_value like "os", "Windows" against
    conan_vars_info.serialize_min()
    """

    def compatible_prop(setting_value, prop_value):
        return (prop_value == setting_value) or (prop_value == "None" and setting_value is None)

    info_settings = conan_vars_info.get("settings", [])
    info_options = conan_vars_info.get("options", [])

    if (prop_name in ["os", "os_build", "compiler", "arch", "arch_build", "build_type"] or
            prop_name.startswith("compiler.")):
        return compatible_prop(info_settings.get(prop_name, None), prop_value)
    else:
        return compatible_prop(info_options.get(prop_name, None), prop_value)


def search_recipes(cache, pattern=None, ignorecase=True):
    # Conan references in main storage
    if pattern:
        if isinstance(pattern, ConanFileReference):
            pattern = str(pattern)
        pattern = translate(pattern)
        pattern = re.compile(pattern, re.IGNORECASE) if ignorecase else re.compile(pattern)

    subdirs = list_folder_subdirs(basedir=cache.store, level=4)
    refs = [ConanFileReference(*folder.split("/")) for folder in subdirs]
    refs.extend(cache.editable_packages.edited_refs.keys())
    if pattern:
        refs = [r for r in refs if _partial_match(pattern, r)]
    refs = sorted(refs)
    return refs


def _partial_match(pattern, ref):
    """
    Finds if pattern matches any of partial sums of tokens of conan reference
    """
    tokens = str(ref).replace('/', ' / ').replace('@', ' @ ').replace('#', ' # ').split()

    def partial_sums(iterable):
        partial = ''
        for i in iterable:
            partial += i
            yield partial

    return any(map(pattern.match, list(partial_sums(tokens))))


def search_packages(package_layout, query):
    """ Return a dict like this:

            {package_ID: {name: "OpenCV",
                           version: "2.14",
                           settings: {os: Windows}}}
    param package_layout: Layout for the given reference
    """
    if not os.path.exists(package_layout.conan()) or (
            package_layout.ref.revision and
            package_layout.recipe_revision() != package_layout.ref.revision):
        raise RecipeNotFoundException(package_layout.ref, print_rev=True)
    infos = _get_local_infos_min(package_layout)
    return filter_packages(query, infos)


def _get_local_infos_min(package_layout):
    result = OrderedDict()

    packages_path = package_layout.packages()
    subdirs = list_folder_subdirs(packages_path, level=1)
    for package_id in subdirs:
        # Read conaninfo
        pref = PackageReference(package_layout.ref, package_id)
        info_path = os.path.join(package_layout.package(pref), CONANINFO)
        if not os.path.exists(info_path):
            logger.error("There is no ConanInfo: %s" % str(info_path))
            continue
        conan_info_content = load(info_path)

        info = ConanInfo.loads(conan_info_content)
        if package_layout.ref.revision:
            metadata = package_layout.load_metadata()
            recipe_revision = metadata.packages[package_id].recipe_revision
            if recipe_revision and recipe_revision != package_layout.ref.revision:
                continue
        conan_vars_info = info.serialize_min()
        result[package_id] = conan_vars_info

    return result
