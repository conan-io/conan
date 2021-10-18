from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.search.search import search_recipes


class SearchAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def search_local_recipes(self, query):
        app = ConanApp(self.conan_api.cache_folder)
        references = search_recipes(app.cache, query)
        return references

    @api_method
    def search_remote_recipes(self, query, remote):
        app = ConanApp(self.conan_api.cache_folder)
        app.load_remotes([remote])

        references = app.remote_manager.search_recipes(remote, query)
        return references
