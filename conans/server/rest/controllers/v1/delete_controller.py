import codecs
import json
import os

from bottle import request

from conans.model.ref import ConanFileReference
from conans import DEFAULT_REVISION_V1
from conans.server.rest.bottle_routes import BottleRoutes
from conans.server.rest.controllers.controller import Controller
from conans.server.service.service import ConanService


class DeleteController(Controller):
    """
        Serve requests related with Conan
    """
    def attach_to(self, app):

        r = BottleRoutes(self.route)

        @app.route(r.recipe, method="DELETE")
        def remove_recipe(name, version, username, channel, auth_user):
            """ Remove any existing conanfiles or its packages created.
            Will remove all revisions, packages and package revisions (parent folder)"""
            conan_reference = ConanFileReference(name, version, username, channel)
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            conan_service.remove_conanfile(conan_reference)

        @app.route('%s/delete' % r.packages, method="POST")
        def remove_packages(name, version, username, channel, auth_user):
            """ Remove any existing conanfiles or its packages created """
            conan_reference = ConanFileReference(name, version, username, channel)
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            reader = codecs.getreader("utf-8")
            payload = json.load(reader(request.body))
            conan_service.remove_packages(conan_reference, payload["package_ids"])

        @app.route('%s/remove_files' % r.recipe, method="POST")
        def remove_recipe_files(name, version, username, channel, auth_user):
            """ Remove any existing conanfiles or its packages created """
            # The remove files is a part of the upload process, where the revision in v1 will always
            # be DEFAULT_REVISION_V1
            revision = DEFAULT_REVISION_V1
            conan_reference = ConanFileReference(name, version, username, channel, revision)
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            reader = codecs.getreader("utf-8")
            payload = json.load(reader(request.body))
            files = [os.path.normpath(filename) for filename in payload["files"]]
            conan_service.remove_conanfile_files(conan_reference, files)
