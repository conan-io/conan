import re

from abc import ABCMeta, abstractmethod
from fnmatch import translate

from conans.errors import ConanException, NotFoundException
from conans.model.info import ConanInfo
from conans.model.ref import PackageReference, ConanFileReference
from conans.paths import CONANINFO
from conans.util.log import logger
import os


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


class DiskSearchManager(SearchManagerABC):
    """Will search recipes and packages using a file system.
    Can be used with a SearchAdapter"""

    def __init__(self, paths, disk_search_adapter):
        self._paths = paths
        self._adapter = disk_search_adapter

    def search(self, pattern=None, ignorecase=True):
        # Conan references in main storage
        if pattern:
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
        # GET PROPERTIES FROM QUERY
        properties = get_properties_from_query(query)

        logger.debug("SEARCH PACKAGE PROPERTIES: %s" % properties)
        result = {}
        packages_path = self._paths.packages(reference)
        subdirs = self._adapter.list_folder_subdirs(packages_path, level=1)
        for package_id in subdirs:
            try:
                package_reference = PackageReference(reference, package_id)
                info_path = self._adapter.join_paths(self._paths.package(package_reference,
                                                                         short_paths=None),
                                                     CONANINFO)
                if not self._adapter.path_exists(info_path):
                    raise NotFoundException("")
                conan_info_content = self._adapter.load(info_path)
                conan_vars_info = ConanInfo.loads(conan_info_content)
                if not self._filtered_by_properties(conan_vars_info, properties):
                    result[package_id] = conan_vars_info.serialize_min()
            except Exception as exc:
                logger.error("Package %s has not ConanInfo file" % str(package_reference))
                if str(exc):
                    logger.error(str(exc))

        return result

    def _filtered_by_properties(self, conan_vars_info, properties):

        def compatible_prop(setting_value, prop_value):
            return setting_value is None or prop_value == setting_value

        for prop_name, prop_value in properties.items():
            if prop_name == "os":
                if compatible_prop(conan_vars_info.settings.os, prop_value):
                    continue
                return True
            elif prop_name == "compiler":
                if compatible_prop(conan_vars_info.settings.compiler, prop_value):
                    continue
                return True
            elif prop_name.startswith("compiler."):
                subsetting = prop_name[9:]
                prop = getattr(conan_vars_info.settings.compiler, subsetting)
                if compatible_prop(prop, prop_value):
                    continue
                return True
            elif prop_name == "arch":
                if compatible_prop(conan_vars_info.settings.arch, prop_value):
                    continue
                return True
            elif prop_name == "build_type":
                if compatible_prop(conan_vars_info.settings.build_type, prop_value):
                    continue
                return True
            else:
                if hasattr(conan_vars_info.options, prop_name):
                    if getattr(conan_vars_info.options, prop_name) == prop_value:
                        continue
                    return True
        return False


def get_properties_from_query(query):
    properties = {}
    if query:
        query = query.replace("AND", "and").replace("and", ",").replace(" ", "")
        for pair in query.split(","):
            try:
                name, value = pair.split("=")
                properties[name] = value
            except ValueError as exc:
                logger.error(exc)
                raise ConanException("Invalid package query: %s" % query)
    return properties
