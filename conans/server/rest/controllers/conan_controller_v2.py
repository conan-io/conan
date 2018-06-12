from bottle import request

from conans.errors import NotFoundException
from conans.model.ref import ConanFileReference, PackageReference
from conans.server.rest.controllers.controller import Controller
from conans.server.service.service_v2 import ConanServiceV2


class ConanControllerV2(Controller):

    def attach_to(self, app):

        recipe_route = '%s/<name>/<version>/<username>/<channel>' % self.route
        recipe_route_rev = '%s/<name>/<version>/<username>/<channel>#<revision>' % self.route
        package_route = '%s/<name>/<version>/<username>/<channel>/packages/<package_id>' % self.route
        package_route_rev = '%s/<name>/<version>/<username>/<channel>#<revision>/packages/' \
                            '<package_id>#<p_revision>' % self.route

        conan_service = ConanServiceV2(app.authorizer, app.server_store, app.revisions_enabled)

        @app.route("%s" % package_route, method=["GET"])
        @app.route("%s" % package_route_rev, method=["GET"])
        def get_package_files_list(name, version, username, channel, package_id, auth_user,
                                   revision=None, p_revision=None):

            reference = ConanFileReference(name, version, username, channel, revision)
            package_reference = PackageReference(reference, package_id, p_revision)
            snapshot = conan_service.get_package_files_list(package_reference, auth_user)
            return snapshot

        @app.route("%s/<the_path:path>" % package_route, method=["GET"])
        @app.route("%s/<the_path:path>" % package_route_rev, method=["GET"])
        def get_package_file(name, version, username, channel, package_id, the_path, auth_user,
                             revision=None, p_revision=None):
            reference = ConanFileReference(name, version, username, channel, revision)
            package_reference = PackageReference(reference, package_id, p_revision)
            file_generator = conan_service.get_package_file(package_reference, the_path, auth_user)
            return file_generator

        @app.route('%s/<the_path:path>' % package_route_rev, method=["PUT"])
        def upload_package_file(name, version, username, channel, package_id,
                                the_path, auth_user, revision=None, p_revision=None):

            if "X-Checksum-Deploy" in request.headers:
                raise NotFoundException("Non checksum storage")
            reference = ConanFileReference(name, version, username, channel, revision)
            package_reference = PackageReference(reference, package_id, p_revision)
            conan_service.upload_package_file(request.body, request.headers, package_reference,
                                              the_path, auth_user)

        @app.route("%s" % recipe_route, method=["GET"])
        @app.route("%s" % recipe_route_rev, method=["GET"])
        def get_conanfile_files_list(name, version, username, channel, auth_user, revision=None):

            reference = ConanFileReference(name, version, username, channel, revision)
            snapshot = conan_service.get_conanfile_files_list(reference, auth_user)
            return snapshot

        @app.route("%s/<the_path:path>" % recipe_route, method=["GET"])
        @app.route("%s/<the_path:path>" % recipe_route_rev, method=["GET"])
        def get_recipe_file(name, version, username, channel, the_path, auth_user, revision=None):
            reference = ConanFileReference(name, version, username, channel, revision)
            file_generator = conan_service.get_conanfile_file(reference, the_path, auth_user)
            return file_generator

        @app.route('%s/<the_path:path>' % recipe_route_rev, method=["PUT"])
        def upload_recipe_file(name, version, username, channel, the_path, auth_user,
                               revision=None):
            if "X-Checksum-Deploy" in request.headers:
                raise NotFoundException("Not a checksum storage")
            reference = ConanFileReference(name, version, username, channel, revision)
            conan_service.upload_recipe_file(request.body, request.headers, reference, the_path,
                                             auth_user)
