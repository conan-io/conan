import codecs
import json
import os

from bottle import request

from conans.model.ref import ConanFileReference, PackageReference
from conans.server.rest.controllers.controller import Controller
from conans.server.service.service import ConanService


class DeleteController(Controller):
    """
        Serve requests related with Conan
    """
    def attach_to(self, app):

        conan_route = '%s/<conanname>/<version>/<username>/<channel>' % self.route

        @app.route(conan_route, method="DELETE")
        def remove_conanfile(conanname, version, username, channel, auth_user):
            """ Remove any existing conanfiles or its packages created """
            conan_reference = ConanFileReference(conanname, version, username, channel)
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            conan_service.remove_conanfile(conan_reference)

        @app.route('%s/packages/delete' % conan_route, method="POST")
        def remove_packages(conanname, version, username, channel, auth_user):
            """ Remove any existing conanfiles or its packages created """
            conan_reference = ConanFileReference(conanname, version, username, channel)
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reader = codecs.getreader("utf-8")
            payload = json.load(reader(request.body))
            conan_service.remove_packages(conan_reference, payload["package_ids"])

        @app.route('%s/remove_files' % conan_route, method="POST")
        def remove_conanfile_files(conanname, version, username, channel, auth_user):
            """ Remove any existing conanfiles or its packages created """
            conan_reference = ConanFileReference(conanname, version, username, channel)
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reader = codecs.getreader("utf-8")
            payload = json.load(reader(request.body))
            files = [os.path.normpath(filename) for filename in payload["files"]]
            conan_service.remove_conanfile_files(conan_reference, files)

        @app.route('%s/packages/:package_id/remove_files' % conan_route, method=["POST"])
        def remove_packages_files(conanname, version, username, channel, package_id, auth_user):
            """ Remove any existing conanfiles or its packages created """
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reference = ConanFileReference(conanname, version, username, channel)
            package_reference = PackageReference(reference, package_id)
            reader = codecs.getreader("utf-8")
            payload = json.load(reader(request.body))
            files = [os.path.normpath(filename) for filename in payload["files"]]
            conan_service.remove_package_files(package_reference, files)
