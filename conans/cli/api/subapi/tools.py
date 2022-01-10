import copy
import fnmatch
import re

from conans.cli.api.subapi import api_method
from conans.search.search import filter_packages, _partial_match


class ToolsAPI:
    # TODO: Still not sure about this subapi (fear of junk drawer). But necessary functions indeed

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def filter_packages_configurations(self, pkg_configurations, query):
        """
        :param pkg_configurations: Dict[PkgReference, PkgConfiguration]
        :param query: str like "os=Windows AND (arch=x86 OR compiler=gcc)"
        :return: Dict[PkgReference, PkgConfiguration]
        """
        return filter_packages(query, pkg_configurations)

    @api_method
    def is_recipe_matching(self, ref, pattern):
        return fnmatch.fnmatch(ref.repr_notime(), pattern)

    @api_method
    def is_package_matching(self, ref, pattern):
        pass
