from bottle import request

from conans.model.ref import ConanFileReference
from conans.server.rest.controllers.controller import Controller
from conans.server.service.service import SearchService


class SearchControllerV2(Controller):
    """
        Serve requests related with Conan
    """
    def attach_to(self, app):

        recipe_route_rev = '%s/<name>/<version>/<username>/<channel>#<revision>' % self.route
        recipe_route = '%s/<name>/<version>/<username>/<channel>' % self.route

        @app.route('%s/search' % self.route, method=["GET"])
        def search(auth_user):
            # FIXME: Duplicated with apiv1
            pattern = request.params.get("q", None)
            ignorecase = request.params.get("ignorecase", True)
            if isinstance(ignorecase, str):
                ignorecase = False if 'false' == ignorecase.lower() else True
            search_service = SearchService(app.authorizer, app.paths, auth_user)
            references = [str(ref) for ref in search_service.search(pattern, ignorecase)]
            return {"results": references}

        @app.route('%s/search' % recipe_route_rev, method=["GET"])
        @app.route('%s/search' % recipe_route, method=["GET"])
        def search_packages(name, version, username, channel, auth_user, revision=None):
            query = request.params.get("q", None)
            search_service = SearchService(app.authorizer, app.server_store, auth_user)
            conan_reference = ConanFileReference(name, version, username, channel, revision)
            info = search_service.search_packages(conan_reference, query)
            return info
