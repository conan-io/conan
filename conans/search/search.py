import re
import os

from fnmatch import translate

from conans.errors import ConanException, NotFoundException
from conans.model.info import ConanInfo
from conans.model.ref import PackageReference, ConanFileReference
from conans.paths import CONANINFO
from conans.util.log import logger
from conans.search.query_parse import infix_to_postfix, evaluate_postfix
from conans.util.files import list_folder_subdirs, load


def filter_outdated(packages_infos, recipe_hash):
    result = {}
    for package_id, info in packages_infos.items():
        try:  # Existing package_info of old package might not have recipe_hash
            if info["recipe_hash"] != recipe_hash:
                result[package_id] = info
        except KeyError:
            pass
    return result


def filter_packages(query, package_infos):
    if query is None:
        return package_infos
    try:
        if "!" in query:
            raise ConanException("'!' character is not allowed")
        if " not " in query or query.startswith("not "):
            raise ConanException("'not' operator is not allowed")
        postfix = infix_to_postfix(query) if query else []
        result = {}
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
    Evaluates a single prop_name, prop_value like "os", "Windows" against conan_vars_info.serialize_min()
    """

    def compatible_prop(setting_value, prop_value):
        return (prop_value == setting_value) or (prop_value == "None" and setting_value is None)

    info_settings = conan_vars_info.get("settings", [])
    info_options = conan_vars_info.get("options", [])

    if prop_name in ["os", "compiler", "arch", "build_type"] or prop_name.startswith("compiler."):
        return compatible_prop(info_settings.get(prop_name, None), prop_value)
    else:
        return compatible_prop(info_options.get(prop_name, None), prop_value)
    return False


def search_recipes(paths, pattern=None, ignorecase=True):
    # Conan references in main storage
    if pattern:
        if isinstance(pattern, ConanFileReference):
            pattern = str(pattern)
        pattern = translate(pattern)
        pattern = re.compile(pattern, re.IGNORECASE) if ignorecase else re.compile(pattern)

    subdirs = list_folder_subdirs(basedir=paths.store, level=4)
    if not pattern:
        return sorted([ConanFileReference(*folder.split("/")) for folder in subdirs])
    else:
        ret = []
        for subdir in subdirs:
            conan_ref = ConanFileReference(*subdir.split("/"))
            if _partial_match(pattern, conan_ref):
                ret.append(conan_ref)

        return sorted(ret)


def _partial_match(pattern, conan_ref):
    """
    Finds if pattern matches any of partial sums of tokens of conan reference
    """
    tokens = str(conan_ref).replace('/', ' / ').replace('@', ' @ ').split()

    def partial_sums(iterable):
        partial = ''
        for i in iterable:
            partial += i
            yield partial

    return any(map(pattern.match, list(partial_sums(tokens))))


def search_packages(paths, reference, query):
    """ Return a dict like this:

            {package_ID: {name: "OpenCV",
                           version: "2.14",
                           settings: {os: Windows}}}
    param conan_ref: ConanFileReference object
    """
    if not os.path.exists(paths.conan(reference)):
        raise NotFoundException("Recipe not found: %s" % str(reference))
    infos = _get_local_infos_min(paths, reference)
    return filter_packages(query, infos)


def _get_local_infos_min(paths, reference):
    result = {}
    packages_path = paths.packages(reference)
    subdirs = list_folder_subdirs(packages_path, level=1)
    for package_id in subdirs:
        # Read conaninfo
        try:
            package_reference = PackageReference(reference, package_id)
            info_path = os.path.join(paths.package(package_reference,
                                                   short_paths=None), CONANINFO)
            if not os.path.exists(info_path):
                raise NotFoundException("")
            conan_info_content = load(info_path)
            conan_vars_info = ConanInfo.loads(conan_info_content).serialize_min()
            result[package_id] = conan_vars_info

        except Exception as exc:
            logger.error("Package %s has no ConanInfo file" % str(package_reference))
            if str(exc):
                logger.error(str(exc))
    return result
