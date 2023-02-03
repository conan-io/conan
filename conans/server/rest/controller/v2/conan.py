from bottle import request

from conans.errors import NotFoundException
from conans.model.recipe_ref import RecipeReference
from conans.server.rest.bottle_routes import BottleRoutes
from conans.server.rest.controller.v2 import get_package_ref
from conans.server.service.v2.service_v2 import ConanServiceV2


class ConanControllerV2(object):

    @staticmethod
    def attach_to(app):

        conan_service = ConanServiceV2(app.authorizer, app.server_store)
        r = BottleRoutes()

        @app.route(r.package_revision_files, method=["GET"])
        def get_package_file_list(name, version, username, channel, package_id, auth_user,
                                  revision, p_revision):
            pref = get_package_ref(name, version, username, channel, package_id,
                                   revision, p_revision)
            ret = conan_service.get_package_file_list(pref, auth_user)
            return ret

        @app.route(r.package_revision_file, method=["GET"])
        def get_package_file(name, version, username, channel, package_id, the_path, auth_user,
                             revision, p_revision):
            pref = get_package_ref(name, version, username, channel, package_id,
                                   revision, p_revision)
            file_generator = conan_service.get_package_file(pref, the_path, auth_user)
            return file_generator

        @app.route(r.package_revision_file, method=["PUT"])
        def upload_package_file(name, version, username, channel, package_id,
                                the_path, auth_user, revision, p_revision):

            if "X-Checksum-Deploy" in request.headers:
                raise NotFoundException("Non checksum storage")
            pref = get_package_ref(name, version, username, channel, package_id,
                                   revision, p_revision)
            conan_service.upload_package_file(request.body, request.headers, pref,
                                              the_path, auth_user)

        @app.route(r.recipe_revision_files, method=["GET"])
        def get_recipe_file_list(name, version, username, channel, auth_user, revision):
            ref = RecipeReference(name, version, username, channel, revision)
            ret = conan_service.get_recipe_file_list(ref, auth_user)
            return ret

        @app.route(r.recipe_revision_file, method=["GET"])
        def get_recipe_file(name, version, username, channel, the_path, auth_user, revision):
            ref = RecipeReference(name, version, username, channel, revision)
            file_generator = conan_service.get_recipe_file(ref, the_path, auth_user)
            return file_generator

        @app.route(r.recipe_revision_file, method=["PUT"])
        def upload_recipe_file(name, version, username, channel, the_path, auth_user, revision):
            if "X-Checksum-Deploy" in request.headers:
                raise NotFoundException("Not a checksum storage")
            ref = RecipeReference(name, version, username, channel, revision)
            conan_service.upload_recipe_file(request.body, request.headers, ref, the_path, auth_user)
