from collections import OrderedDict

from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.errors import NotFoundException, PackageNotFoundException, ConanException


class SearchAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def search_local_recipes(self, query):
        app = ConanApp(self.conan_api.cache_folder)
        app.load_remotes()
        references = app.proxy.search_recipes(query)
        results = []
        for reference in references:
            result = {
                "name": reference.name,
                "id": repr(reference)
            }
            results.append(result)
        return results

    @api_method
    def search_remote_recipes(self, query, remotes):
        app = ConanApp(self.conan_api.cache_folder)
        if not remotes:
            raise ConanException("Specify the 'remotes' argument")
        app.load_remotes(remotes)
        # CUANDO FUNCIONE ESTO SEGUIR CON EL USER QUE LO QUIERO METER AL REMOTE:
        # conan remote user-list
        # conan remote login remote [--user] [--password] --skip-auth
        # conan remote logout -r remote -r remote (sin -r logout de todo?)


        results = []

        for remote in app.enabled_remotes:
            error = None
            try:
                remote_references = OrderedDict()
                refs = app.remote_manager.search_recipes(remote, query)
                remote_references[remote.name] = sorted(refs)

                remote_results = []
                for remote_name, references in remote_references.items():
                    for reference in references:
                        doc = {
                            "name": reference.name,
                            "id": repr(reference)
                        }
                        remote_results.append(doc)
            except (NotFoundException, PackageNotFoundException):
                # This exception must be caught manually due to a server inconsistency:
                # Artifactory API returns an empty result if the recipe doesn't exist, but
                # Conan Server returns a 404. This probably should be fixed server side,
                # but in the meantime we must handle it here
                result = {}
            except ConanException as e:
                error = str(e)
                result = {}

            results.append({
                "remote": remote.name,
                "error": error,
                "results": remote_results
            })
        return results
