from conan.internal.conan_app import ConanApp
from conans.search.search import search_recipes


class SearchAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

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
