from conans.model.ref import ConanFileReference, PackageReference
from conans.server.rest.controllers.controller import Controller
from conans.server.service.service import ConanService


class ConanControllerV2(Controller):


!!! pass the revisions config (from previous pr?)

    def attach_to(self, app):

        recipe_route = '%s/<conanname>/<version>/<username>/<channel>' % self.route
        package_route = '%s/<conanname>/<version>/<username>/<channel>/<package_id>/' % self.route

        @app.route("%s/list" % recipe_route, method=["GET"])
        def get_conanfile_files_list(name, version, username, channel, auth_user):
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reference = ConanFileReference(name, version, username, channel)
            snapshot = conan_service.get_conanfile_snapshot(reference)
            snapshot_norm = {"files": {filename.replace("\\", "/"): the_md5
                                       for filename, the_md5 in snapshot.items()},
                             "recipe_hash": "PENDING"}
            return snapshot_norm

        @app.route('%s/list' % package_route, method=["GET"])
        def get_package_files_list(name, version, username, channel, package_id, auth_user):
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reference = ConanFileReference(name, version, username, channel)
            package_reference = PackageReference(reference, package_id)
            snapshot = conan_service.get_package_snapshot(package_reference)
            snapshot_norm = {"files": {filename.replace("\\", "/"): the_md5
                                       for filename, the_md5 in snapshot.items()},
                             "recipe_hash": "PENDING"}
            return snapshot_norm

