import copy
import os
import re
from fnmatch import translate

from conan.api.output import ConanOutput
from conans.errors import NotFoundException, ForbiddenException, RecipeNotFoundException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.paths import CONANINFO
from conans.search.search import _partial_match
from conans.server.utils.files import list_folder_subdirs
from conans.util.files import load


def _get_local_infos_min(server_store, ref, look_in_all_rrevs):

    result = {}
    rrevs = server_store.get_recipe_revisions_references(ref) if look_in_all_rrevs else [None]

    for rrev in rrevs:
        new_ref = copy.copy(ref)
        if rrev:
            new_ref.revision = rrev.revision
        subdirs = list_folder_subdirs(server_store.packages(new_ref), level=1)
        for package_id in subdirs:
            if package_id in result:
                continue
            # Read conaninfo
            try:
                pref = PkgReference(new_ref, package_id)
                revision_entry = server_store.get_last_package_revision(pref)
                if not revision_entry:
                    raise NotFoundException("")
                pref.revision = revision_entry.revision
                info_path = os.path.join(server_store.package(pref), CONANINFO)
                if not os.path.exists(info_path):
                    raise NotFoundException("")
                content = load(info_path)
                # From Conan 1.48 the conaninfo.txt is sent raw.
                result[package_id] = {"content": content}
            except Exception as exc:  # FIXME: Too wide
                ConanOutput().error("Package %s has no ConanInfo file" % str(pref))
                if str(exc):
                    ConanOutput().error(str(exc))
    return result


def search_packages(server_store, ref, look_in_all_rrevs):
    """
    Used both for v1 and v2. V1 will iterate rrevs.

    Return a dict like this:

            {package_ID: {name: "OpenCV",
                           version: "2.14",
                           settings: {os: Windows}}}
    param ref: RecipeReference object
    """
    if not look_in_all_rrevs and ref.revision is None:
        latest_rev = server_store.get_last_revision(ref).revision
        ref.revision = latest_rev

    ref_norev = copy.copy(ref)
    ref_norev.revision = None
    if not os.path.exists(server_store.conan_revisions_root(ref_norev)):
        raise RecipeNotFoundException(ref)
    infos = _get_local_infos_min(server_store, ref, look_in_all_rrevs)
    return infos


class SearchService(object):

    def __init__(self, authorizer, server_store, auth_user):
        self._authorizer = authorizer
        self._server_store = server_store
        self._auth_user = auth_user

    def search_packages(self, reference, look_in_all_rrevs=False):
        """Shared between v1 and v2, v1 will iterate rrevs"""
        self._authorizer.check_read_conan(self._auth_user, reference)
        info = search_packages(self._server_store, reference, look_in_all_rrevs)
        return info

    def _search_recipes(self, pattern=None, ignorecase=True):
        subdirs = list_folder_subdirs(basedir=self._server_store.store, level=5)

        def underscore_to_none(field):
            return field if field != "_" else None

        if not pattern:
            ret = []
            for folder in subdirs:
                fields_dir = [underscore_to_none(d) for d in folder.split("/")]
                r = RecipeReference(*fields_dir)
                r.revision = None
                ret.append(r)
            return sorted(ret)
        else:
            # Conan references in main storage
            pattern = str(pattern)
            b_pattern = translate(pattern)
            b_pattern = re.compile(b_pattern, re.IGNORECASE) if ignorecase else re.compile(b_pattern)
            ret = set()
            for subdir in subdirs:
                fields_dir = [underscore_to_none(d) for d in subdir.split("/")]
                new_ref = RecipeReference(*fields_dir)
                new_ref.revision = None
                if _partial_match(b_pattern, repr(new_ref)):
                    ret.add(new_ref)

            return sorted(ret)

    def search(self, pattern=None, ignorecase=True):
        """ Get all the info about any package
            Attributes:
                pattern = wildcards like opencv/*
        """
        refs = self._search_recipes(pattern, ignorecase)
        filtered = []
        # Filter out restricted items
        for ref in refs:
            try:
                self._authorizer.check_read_conan(self._auth_user, ref)
                filtered.append(ref)
            except ForbiddenException:
                pass
        return filtered
