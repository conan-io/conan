from bottle import request

from conans.errors import NotFoundException
from conans.model.ref import ConanFileReference, PackageReference
from conans.server.rest.controllers.controller import Controller
from conans.server.rest.controllers.routes import Router
from conans.server.service.service_v2 import ConanServiceV2


class ConanControllerV2(Controller):

    def attach_to(self, app):

        conan_service = ConanServiceV2(app.authorizer, app.server_store)
        r = Router(self.route)

        @app.route(r.package, method=["GET"])
        @app.route(r.package_recipe_revision, method=["GET"])
        @app.route(r.package_revision, method=["GET"])
        def get_package_file_list(name, version, username, channel, package_id, auth_user,
                                  revision=None, p_revision=None):

            package_reference = get_package_ref(name, version, username, channel, package_id,
                                                revision, p_revision)
            ret = conan_service.get_package_file_list(package_reference, auth_user)
            return ret

        @app.route(r.package_file, method=["GET"])
        @app.route(r.package_recipe_revision_file, method=["GET"])
        @app.route(r.package_revision_file, method=["GET"])
        def get_package_file(name, version, username, channel, package_id, the_path, auth_user,
                             revision=None, p_revision=None):
            package_reference = get_package_ref(name, version, username, channel, package_id,
                                                revision, p_revision)
            file_generator = conan_service.get_package_file(package_reference, the_path, auth_user)
            return file_generator

        @app.route(r.package_file, method=["PUT"])
        @app.route(r.package_revision_file, method=["PUT"])
        def upload_package_file(name, version, username, channel, package_id,
                                the_path, auth_user, revision=None, p_revision=None):

            if "X-Checksum-Deploy" in request.headers:
                raise NotFoundException("Non checksum storage")
            package_reference = get_package_ref(name, version, username, channel, package_id,
                                                revision, p_revision)
            conan_service.upload_package_file(request.body, request.headers, package_reference,
                                              the_path, auth_user)

        @app.route(r.recipe, method=["GET"])
        @app.route(r.recipe_revision, method=["GET"])
        def get_recipe_file_list(name, version, username, channel, auth_user, revision=None):

            reference = ConanFileReference(name, version, username, channel, revision)
            ret = conan_service.get_recipe_file_list(reference, auth_user)
            return ret

        @app.route(r.recipe_file, method=["GET"])
        @app.route(r.recipe_revision_file, method=["GET"])
        def get_recipe_file(name, version, username, channel, the_path, auth_user, revision=None):
            reference = ConanFileReference(name, version, username, channel, revision)
            file_generator = conan_service.get_conanfile_file(reference, the_path, auth_user)
            return file_generator

        @app.route(r.recipe_file, method=["PUT"])
        @app.route(r.recipe_revision_file, method=["PUT"])
        def upload_recipe_file(name, version, username, channel, the_path, auth_user,
                               revision=None):
            if "X-Checksum-Deploy" in request.headers:
                raise NotFoundException("Not a checksum storage")
            reference = ConanFileReference(name, version, username, channel, revision)
            conan_service.upload_recipe_file(request.body, request.headers, reference, the_path,
                                             auth_user)


def get_package_ref(name, version, username, channel, package_id, revision, p_revision):
    reference = ConanFileReference(name, version, username, channel, revision)
    package_id = "%s#%s" % (package_id, p_revision) if p_revision else package_id
    return PackageReference(reference, package_id)
