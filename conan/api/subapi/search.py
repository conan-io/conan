import fnmatch

from conan.api.model import SelectBundle
from conan.api.subapi import api_method
from conan.api.conan_app import ConanApp
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

    def select(self, ref_pattern, only_recipe=False, package_query=None, remote=None):
        select_bundle = SelectBundle()
        refs = self.conan_api.search.recipes(ref_pattern.ref)
        for r in refs:
            if ref_pattern.rrev is None:  # latest
                rrevs = [self.conan_api.list.latest_recipe_revision(r, remote)]
            else:
                rrevs = self.conan_api.list.recipe_revisions(r, remote)
                rrevs = [r for r in rrevs if fnmatch.fnmatch(r.revision, ref_pattern.rrev)]

            # Add recipe revisions to bundle
            for rrev in rrevs:
                select_bundle.add_ref(rrev)
                if only_recipe:
                    continue
                prefs = self.conan_api.list.packages_configurations(rrev, remote)
                if package_query is not None:
                    prefs = self.conan_api.list.filter_packages_configurations(prefs, package_query)
                prefs = prefs.keys()
                if ref_pattern.pid is not None:
                    prefs = [p for p in prefs if fnmatch.fnmatch(p.package_id, ref_pattern.pid)]

                for pref in prefs:
                    if ref_pattern.prev is None:  # latest
                        prevs = [self.conan_api.list.latest_package_revision(pref, remote)]
                    else:
                        prevs = self.conan_api.list.package_revisions(pref, remote)
                        prevs = [p for p in prevs if fnmatch.fnmatch(p.revision, ref_pattern.prev)]
                    select_bundle.add_prefs(prevs)
        return select_bundle
