from conans.model.recipe_ref import RecipeReference
from conans.server.rest.bottle_routes import BottleRoutes
from conans.server.rest.controller.v2 import get_package_ref
from conans.server.service.v2.service_v2 import ConanServiceV2


class DeleteControllerV2(object):
    """
        Serve requests related with Conan
    """
    @staticmethod
    def attach_to(app):

        r = BottleRoutes()

        @app.route(r.recipe, method="DELETE")
        @app.route(r.recipe_revision, method="DELETE")
        def remove_recipe(name, version, username, channel, auth_user, revision=None):
            """ Remove any existing conanfiles or its packages created.
            Will remove all revisions, packages and package revisions (parent folder) if no revision
            is passed
            """
            ref = RecipeReference(name, version, username, channel, revision)
            conan_service = ConanServiceV2(app.authorizer, app.server_store)
            conan_service.remove_recipe(ref, auth_user)

        @app.route(r.package_recipe_revision, method=["DELETE"])
        @app.route(r.package_revision, method=["DELETE"])
        def remove_package(name, version, username, channel, package_id, auth_user,
                           revision=None, p_revision=None):
            """ - If both RRev and PRev are specified, it will remove the specific package revision
                  of the specific recipe revision.
                - If PRev is NOT specified but RRev is specified (package_recipe_revision_url)
                  it will remove all the package revisions
             """
            pref = get_package_ref(name, version, username, channel, package_id,
                                   revision, p_revision)
            conan_service = ConanServiceV2(app.authorizer, app.server_store)
            conan_service.remove_package(pref, auth_user)

        @app.route(r.packages_revision, method="DELETE")
        def remove_all_packages(name, version, username, channel, auth_user, revision=None):
            """ Remove all packages from a RREV"""
            ref = RecipeReference(name, version, username, channel, revision)
            conan_service = ConanServiceV2(app.authorizer, app.server_store)
            conan_service.remove_all_packages(ref, auth_user)
