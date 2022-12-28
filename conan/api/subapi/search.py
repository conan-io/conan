from conan.api.model import SelectBundle
from conan.api.subapi import api_method
from conan.internal.conan_app import ConanApp
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.search.search import search_recipes


class SearchAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def recipes(self, query: str, remote=None):
        only_none_user_channel = False
        if query and query.endswith("@"):
            only_none_user_channel = True
            query = query[:-1]

        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            refs = app.remote_manager.search_recipes(remote, query)
        else:
            references = search_recipes(app.cache, query)
            # For consistency with the remote search, we return references without revisions
            # user could use further the API to look for the revisions
            refs = []
            for r in references:
                r.revision = None
                r.timestamp = None
                if r not in refs:
                    refs.append(r)
        ret = []
        for r in refs:
            if not only_none_user_channel or (r.user is None and r.channel is None):
                ret.append(r)
        return ret

    def select(self, pattern, only_recipe=False, package_query=None, remote=None):
        if package_query and pattern.package_id and "*" not in pattern.package_id:
            raise ConanException("Cannot specify '-p' package queries, "
                                 "if 'package_id' is not a pattern")

        select_bundle = SelectBundle()
        if pattern.is_ref_pattern():  # Optimization to avoid a search recipes if ref is exact
            refs = self.conan_api.search.recipes(pattern.ref, remote=remote)
            pattern.check_refs(refs)
        else:
            refs = [RecipeReference.loads(pattern.ref)]

        for r in refs:
            if pattern.is_latest_rrev:
                # TODO: This should probably raise an error if r doesn't exist
                latest_rev = self.conan_api.list.latest_recipe_revision(r, remote)
                if latest_rev is None:
                    raise ConanException(f"Recipe '{r}' not found")
                rrevs = [latest_rev]
            else:
                if pattern.rrev is not None and "*" not in pattern.rrev:  # optimization, exact rrev
                    # There is no guarentee the revision will exist, but the servers don't fail
                    # if it doesn't and return empty sets
                    # There is no API for validating existence of rrev
                    # FIXME: Improve and optimize this API
                    rrevs = self.conan_api.list.recipe_revisions(r, remote)
                    r.revision = pattern.rrev
                    if r not in rrevs:
                        raise ConanException(f"Recipe revision '{r.repr_notime()}' not found")
                    rrevs = [r]
                else:
                    rrevs = self.conan_api.list.recipe_revisions(r, remote)
                    rrevs = pattern.filter_rrevs(rrevs)

            select_bundle.add_refs(rrevs)
            # Add recipe revisions to bundle
            for rrev in rrevs:
                if only_recipe:
                    continue
                if pattern.package_id is not None and "*" not in pattern.package_id:
                    # optimization, exact pid
                    pref = PkgReference(rrev, pattern.package_id)
                    # FIXME: This is a problem, it returns [] even for missing, non existing rrevs
                    # FIXME: This is bad API, because we don't have API for checking if PID exists
                    prefs = self.conan_api.list.packages_configurations(rrev, remote)
                    if pref not in prefs:
                        raise ConanException(f"Package ID '{pref.repr_notime()}' not found")
                    prefs = [pref]
                else:
                    # FIXME: This is a problem, it returns [] even for missing, non existing rrevs
                    prefs = self.conan_api.list.packages_configurations(rrev, remote)
                    if package_query is not None:
                        prefs = self.conan_api.list.filter_packages_configurations(prefs,
                                                                                   package_query)
                    prefs = prefs.keys()
                    if pattern.package_id is not None:
                        prefs = pattern.filter_prefs(prefs)

                for pref in prefs:
                    if pattern.is_latest_prev:
                        prevs = [self.conan_api.list.latest_package_revision(pref, remote)]
                    else:
                        prevs = self.conan_api.list.package_revisions(pref, remote)
                        prevs = pattern.filter_prevs(prevs)
                    select_bundle.add_prefs(prevs)
        return select_bundle
