import codecs
import json
import os

from bottle import request

from conans.model.ref import ConanFileReference, PackageReference
from conans.server.rest.controllers.controller import Controller
from conans.server.rest.controllers.routes import Router
from conans.server.service.service import ConanService


class DeleteController(Controller):
    """
        Serve requests related with Conan
    """
    def attach_to(self, app):

        r = Router(self.route)

        @app.route(r.recipe, method="DELETE")
        @app.route(r.recipe_revision, method="DELETE")
        def remove_conanfile(name, version, username, channel, auth_user, revision=None):
            """ Remove any existing conanfiles or its packages created """
            conan_reference = ConanFileReference(name, version, username, channel, revision)
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            conan_service.remove_conanfile(conan_reference)

        @app.route('%s/delete' % r.packages, method="POST")
        @app.route('%s/delete' % r.packages_revision, method="POST")
        def remove_packages(name, version, username, channel, auth_user, revision=None):
            """ Remove any existing conanfiles or its packages created """
            conan_reference = ConanFileReference(name, version, username, channel, revision)
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            reader = codecs.getreader("utf-8")
            payload = json.load(reader(request.body))
            conan_service.remove_packages(conan_reference, payload["package_ids"])

        @app.route('%s/remove_files' % r.recipe, method="POST")
        @app.route('%s/remove_files' % r.recipe_revision, method="POST")
        def remove_conanfile_files(name, version, username, channel, auth_user, revision=None):
            """ Remove any existing conanfiles or its packages created """
            conan_reference = ConanFileReference(name, version, username, channel, revision)
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            reader = codecs.getreader("utf-8")
            payload = json.load(reader(request.body))
            files = [os.path.normpath(filename) for filename in payload["files"]]
            conan_service.remove_conanfile_files(conan_reference, files)
