import codecs
import json
import os

from bottle import request

from conans import DEFAULT_REVISION_V1
from conans.model.ref import ConanFileReference
from conans.server.rest.bottle_routes import BottleRoutes
from conans.server.service.v1.service import ConanService


class DeleteController(object):
    """
        Serve requests related with Conan
    """
    @staticmethod
    def attach_to(app):

        r = BottleRoutes()

        @app.route(r.recipe, method="DELETE")
        def remove_recipe(name, version, username, channel, auth_user):
            """ Remove any existing recipes or its packages created.
            Will remove all revisions, packages and package revisions (parent folder)"""
            ref = ConanFileReference(name, version, username, channel)
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            conan_service.remove_conanfile(ref)

        @app.route('%s/delete' % r.packages, method="POST")
        def remove_packages(name, version, username, channel, auth_user):
            ref = ConanFileReference(name, version, username, channel)
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            reader = codecs.getreader("utf-8")
            payload = json.load(reader(request.body))
            conan_service.remove_packages(ref, payload["package_ids"])

        @app.route('%s/remove_files' % r.recipe, method="POST")
        def remove_recipe_files(name, version, username, channel, auth_user):
            # The remove files is a part of the upload process, where the revision in v1 will
            # always be DEFAULT_REVISION_V1
            revision = DEFAULT_REVISION_V1
            ref = ConanFileReference(name, version, username, channel, revision)
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            reader = codecs.getreader("utf-8")
            payload = json.load(reader(request.body))
            files = [os.path.normpath(filename) for filename in payload["files"]]
            conan_service.remove_conanfile_files(ref, files)
