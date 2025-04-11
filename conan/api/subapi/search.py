from conan.internal.conan_app import ConanBasicApp


class SearchAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def recipes(self, query: str, remote=None):
        only_none_user_channel = False
        if query and query.endswith("@"):
            only_none_user_channel = True
            query = query[:-1]

        app = ConanBasicApp(self.conan_api)
        if remote:
            refs = app.remote_manager.search_recipes(remote, query)
        else:
            refs = app.cache.search_recipes(query)
        ret = []
        for r in refs:
            if not only_none_user_channel or (r.user is None and r.channel is None):
                ret.append(r)
        return sorted(ret)
