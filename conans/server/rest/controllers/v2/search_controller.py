from bottle import request

from conans.model.ref import ConanFileReference
from conans.server.rest.bottle_routes import BottleRoutes
from conans.server.rest.controllers.controller import Controller
from conans.server.service.service import SearchService


class SearchControllerV2(Controller):
    """
        Serve requests related with Conan
    """
    def attach_to(self, app):

        r = BottleRoutes(self.route)

        @app.route('%s/search' % r.base_url, method=["GET"])
        def search(auth_user):
            pattern = request.params.get("q", None)
            ignorecase = request.params.get("ignorecase", True)
            if isinstance(ignorecase, str):
                ignorecase = False if 'false' == ignorecase.lower() else True
            search_service = SearchService(app.authorizer, app.server_store, auth_user)
            references = [ref.full_repr() for ref in search_service.search(pattern, ignorecase)]
            return {"results": references}

        @app.route('%s/search' % r.recipe, method=["GET"])
        @app.route('%s/search' % r.recipe_revision, method=["GET"])
        def search_packages(name, version, username, channel, auth_user, revision=None):
            v2_compatibility_mode = request.headers.get("V2_COMPATIBILITY_MODE", "0") == "1"
            query = request.params.get("q", None)
            search_service = SearchService(app.authorizer, app.server_store, auth_user)
            conan_reference = ConanFileReference(name, version, username, channel, revision)
            info = search_service.search_packages(conan_reference, query, v2_compatibility_mode)
            return info
