from collections import OrderedDict

from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.errors import NotFoundException, PackageNotFoundException, ConanException
from conans.search.search import search_recipes


class SearchAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def search_local_recipes(self, query):
        app = ConanApp(self.conan_api.cache_folder)
        app.load_remotes()
        references = search_recipes(app.cache, query)
        return references

    @api_method
    def search_remote_recipes(self, query, remote):
        app = ConanApp(self.conan_api.cache_folder)
        app.load_remotes([remote])
        # CUANDO FUNCIONE ESTO SEGUIR CON EL USER QUE LO QUIERO METER AL REMOTE:
        # conan remote user-list
        # conan remote login remote [--user] [--password] --skip-auth
        # conan remote logout -r remote -r remote (sin -r logout de todo?)

        references = app.remote_manager.search_recipes(remote, query)
        return references
