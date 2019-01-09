from conans.model.ref import ConanFileReference
from conans.server.rest.bottle_routes import BottleRoutes
from conans.server.rest.controllers.controller import Controller
from conans.server.rest.controllers.v2 import get_package_ref
from conans.server.service.service_v2 import ConanServiceV2


class RevisionsController(Controller):
    """
        Serve requests related with Conan
    """
    def attach_to(self, app):

        r = BottleRoutes(self.route)

        @app.route(r.recipe_revisions, method="GET")
        def get_recipe_revisions(name, version, username, channel, auth_user):
            """ Gets a JSON with the revisions for the specified recipe
            """
            conan_reference = ConanFileReference(name, version, username, channel)
            conan_service = ConanServiceV2(app.authorizer, app.server_store, auth_user)
            ret = conan_service.get_recipe_revisions(conan_reference)
            return ret

        @app.route(r.package_revisions, method="GET")
        def get_package_revisions(name, version, username, channel, package_id, auth_user,
                                  revision):
            """ Get a JSON with the revisions for a specified RREV """
            package_reference = get_package_ref(name, version, username, channel, package_id,
                                                revision, p_revision=None)
            conan_service = ConanServiceV2(app.authorizer, app.server_store, auth_user)
            ret = conan_service.get_package_revisions(package_reference)
            return ret
