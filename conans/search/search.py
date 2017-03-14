import re

from abc import ABCMeta, abstractmethod
from fnmatch import translate

from conans.errors import ConanException, NotFoundException
from conans.model.info import ConanInfo
from conans.model.ref import PackageReference, ConanFileReference
from conans.paths import CONANINFO
from conans.util.log import logger
import os
from conans.search.query_parse import infix_to_postfix, evaluate_postfix


class SearchAdapterABC(object):
    """Methods that allows access to disk or s3 or whatever to make a search"""
    __metaclass__ = ABCMeta

    @abstractmethod
    def list_folder_subdirs(self, basedir, level):
        pass

    @abstractmethod
    def path_exists(self, path):
        pass

    @abstractmethod
    def load(self, filepath):
        pass

    @abstractmethod
    def join_paths(self, *args):
        pass


class DiskSearchAdapter(SearchAdapterABC):

    def list_folder_subdirs(self, basedir, level):
        from conans.util.files import list_folder_subdirs
        return list_folder_subdirs(basedir, level)

    def path_exists(self, path):
        return os.path.exists(path)

    def load(self, filepath):
        from conans.util.files import load
        return load(filepath)

    def join_paths(self, *args):
        return os.path.join(*args)


class SearchManagerABC(object):
    """Methods that allows access to disk or s3 or whatever to make a search"""
    __metaclass__ = ABCMeta

    @abstractmethod
    def search(self, pattern=None, ignorecase=True):
        pass

    @abstractmethod
    def search_packages(self, reference, query):
        pass


def filter_packages(query, package_infos):
    if query is None:
        return package_infos
    try:
        if "!" in query:
            raise ConanException("'!' character is not allowed")
        if " not " in query or query.startswith("not "):
            raise ConanException("'not' operator is not allowed")
        result = {}
        postfix = infix_to_postfix(query) if query else []
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
        return setting_value is None or prop_value == setting_value

    info_settings = conan_vars_info.get("settings", [])
    info_options = conan_vars_info.get("options", [])

    if prop_name in ["os", "compiler", "arch", "build_type"] or prop_name.startswith("compiler."):
        return compatible_prop(info_settings.get(prop_name, None), prop_value)
    else:
        return compatible_prop(info_options.get(prop_name, None), prop_value)
    return False


class DiskSearchManager(SearchManagerABC):
    """Will search recipes and packages using a file system.
    Can be used with a SearchAdapter"""

    def __init__(self, paths, disk_search_adapter):
        self._paths = paths
        self._adapter = disk_search_adapter

    def search(self, pattern=None, ignorecase=True):

        # Conan references in main storage
        if pattern:
            if isinstance(pattern, ConanFileReference):
                pattern = str(pattern)
            pattern = translate(pattern)
            pattern = re.compile(pattern, re.IGNORECASE) if ignorecase else re.compile(pattern)

        subdirs = self._adapter.list_folder_subdirs(basedir=self._paths.store, level=4)
        if not pattern:
            return sorted([ConanFileReference(*folder.split("/")) for folder in subdirs])
        else:
            ret = []
            for subdir in subdirs:
                conan_ref = ConanFileReference(*subdir.split("/"))
                if pattern:
                    if pattern.match(str(conan_ref)):
                        ret.append(conan_ref)
            return sorted(ret)

    def search_packages(self, reference, query):
        """ Return a dict like this:

                {package_ID: {name: "OpenCV",
                               version: "2.14",
                               settings: {os: Windows}}}
        param conan_ref: ConanFileReference object
        """

        infos = self._get_local_infos_min(reference)
        return filter_packages(query, infos)

    def _get_local_infos_min(self, reference):
        result = {}
        packages_path = self._paths.packages(reference)
        subdirs = self._adapter.list_folder_subdirs(packages_path, level=1)
        for package_id in subdirs:
            # Read conaninfo
            try:
                package_reference = PackageReference(reference, package_id)
                info_path = self._adapter.join_paths(self._paths.package(package_reference,
                                                                         short_paths=None),
                                                     CONANINFO)
                if not self._adapter.path_exists(info_path):
                    raise NotFoundException("")
                conan_info_content = self._adapter.load(info_path)
                conan_vars_info = ConanInfo.loads(conan_info_content).serialize_min()
                result[package_id] = conan_vars_info

            except Exception as exc:
                logger.error("Package %s has not ConanInfo file" % str(package_reference))
                if str(exc):
                    logger.error(str(exc))

        return result
