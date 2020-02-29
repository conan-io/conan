from bottle import request

from conans.model.ref import ConanFileReference
from conans.server.rest.bottle_routes import BottleRoutes
from conans.server.service.common.search import SearchService


class SearchController(object):
    """
        Serve requests related with Conan
    """
    @staticmethod
    def attach_to(app):

        r = BottleRoutes()

        @app.route(r.common_search, method=["GET"])
        def search(auth_user):
            pattern = request.params.get("q", None)
            ignore_case = request.params.get("ignorecase", True)
            if isinstance(ignore_case, str):
                ignore_case = False if 'false' == ignore_case.lower() else True
            search_service = SearchService(app.authorizer, app.server_store, auth_user)
            references = [repr(ref) for ref in search_service.search(pattern, ignore_case)]
            return {"results": references}

        @app.route(r.common_search_packages, method=["GET"])
        def search_packages(name, version, username, channel, auth_user):
            query = request.params.get("q", None)
            search_service = SearchService(app.authorizer, app.server_store, auth_user)
            ref = ConanFileReference(name, version, username, channel)
            info = search_service.search_packages(ref, query, look_in_all_rrevs=True)
            return info
