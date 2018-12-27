from conans.model.ref import ConanFileReference
from conans.server.rest.bottle_routes import BottleRoutes
from conans.server.rest.controllers.controller import Controller
from conans.server.rest.controllers.v2 import get_package_ref
from conans.server.service.service import ConanService


class DeleteControllerV2(Controller):
    """
        Serve requests related with Conan
    """
    def attach_to(self, app):

        r = BottleRoutes(self.route)

        @app.route(r.recipe, method="DELETE")
        @app.route(r.recipe_revision, method="DELETE")
        def remove_recipe(name, version, username, channel, auth_user, revision=None):
            """ Remove any existing conanfiles or its packages created.
            Will remove all revisions, packages and package revisions (parent folder) if no revision
            is passed
            """
            conan_reference = ConanFileReference(name, version, username, channel, revision)
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            conan_service.remove_conanfile(conan_reference)

        @app.route(r.package, method="DELETE")
        @app.route(r.package_recipe_revision, method=["DELETE"])
        @app.route(r.package_revision, method=["DELETE"])
        def remove_package(name, version, username, channel, package_id, auth_user,
                           revision=None, p_revision=None):
            """ - If both RRev and PRev are specified, it will remove the specific package revision
                  of the specific recipe revision.
                - If PRev is NOT specified but RRev is specified (package_recipe_revision_url)
                  it will remove all the package revisions
                - If PRev is NOT specified and RRev is NOT specified (package_url) it will remove
                  ALL the package revisions for the specified "package_id" for all the recipe
                  revisions (SAME AS V1)
             """
            package_reference = get_package_ref(name, version, username, channel, package_id,
                                                revision, p_revision)
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            conan_service.remove_package(package_reference)

        @app.route(r.packages, method="DELETE")
        @app.route(r.packages_revision, method="DELETE")
        def remove_all_packages(name, version, username, channel, auth_user, revision=None):
            """ Remove a file from a recipe. The revision is mandatory, because it comes from
            the upload and the revision is mandatory in v2"""
            conan_reference = ConanFileReference(name, version, username, channel, revision)
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            conan_service.remove_all_packages(conan_reference)
