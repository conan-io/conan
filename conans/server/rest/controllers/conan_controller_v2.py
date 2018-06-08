from bottle import request
from conans.model.ref import ConanFileReference, PackageReference
from conans.server.rest.controllers.controller import Controller
from conans.server.service.service_v2 import ConanServiceV2


class ConanControllerV2(Controller):

    def attach_to(self, app):

        recipe_route = '%s/<name>/<version>/<username>/<channel>' % self.route
        package_route = '%s/<name>/<version>/<username>/<channel>/packages/<package_id>' % self.route

        conan_service = ConanServiceV2(app.authorizer, app.server_store, app.revisions_enabled)

        def get_revision_header():
            return request.get_header('CONAN_RECIPE_HASH')

        @app.route("%s" % package_route, method=["GET"])
        def get_package_files_list(name, version, username, channel, package_id, auth_user):

            reference = ConanFileReference(name, version, username, channel)
            package_reference = PackageReference(reference, package_id)
            snapshot = conan_service.get_package_files_list(package_reference,
                                                            get_revision_header(),
                                                            auth_user)
            return snapshot

        @app.route("%s/<the_path:path>" % package_route, method=["GET"])
        def get_package_file(name, version, username, channel, package_id, the_path, auth_user):
            reference = ConanFileReference(name, version, username, channel)
            package_reference = PackageReference(reference, package_id)
            file_generator = conan_service.get_package_file(package_reference, the_path,
                                                            get_revision_header(), auth_user)
            return file_generator

        @app.route('%s/<the_path:path>' % package_route, method=["PUT"])
        def upload_package_file(name, version, username, channel, package_id, the_path, auth_user):

            reference = ConanFileReference(name, version, username, channel)
            package_reference = PackageReference(reference, package_id)
            conan_service.upload_package_file(request.body, request.headers, package_reference,
                                              the_path, get_revision_header(), auth_user)

        @app.route("%s" % recipe_route, method=["GET"])
        def get_conanfile_files_list(name, version, username, channel, auth_user):

            reference = ConanFileReference(name, version, username, channel)
            snapshot = conan_service.get_conanfile_files_list(reference, get_revision_header(),
                                                              auth_user)
            return snapshot

        @app.route("%s/<the_path:path>" % recipe_route, method=["GET"])
        def get_recipe_file(name, version, username, channel, the_path, auth_user):
            reference = ConanFileReference(name, version, username, channel)
            file_generator = conan_service.get_conanfile_file(reference, the_path,
                                                              get_revision_header(), auth_user)
            return file_generator

        @app.route('%s/<the_path:path>' % recipe_route, method=["PUT"])
        def upload_recipe_file(name, version, username, channel, the_path, auth_user):
            reference = ConanFileReference(name, version, username, channel)
            conan_service.upload_recipe_file(request.body, request.headers, reference, the_path,
                                             get_revision_header(), auth_user)
