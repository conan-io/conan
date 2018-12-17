import codecs
import json

from bottle import request

from conans.errors import NotFoundException
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONAN_MANIFEST
from conans import DEFAULT_REVISION_V1
from conans.server.rest.bottle_routes import BottleRoutes
from conans.server.rest.controllers.controller import Controller
from conans.server.service.service import ConanService


class ConanController(Controller):
    """
        Serve requests related with Conan
    """
    def attach_to(self, app):

        r = BottleRoutes(self.route)

        @app.route(r.v1_recipe_digest, method=["GET"])
        def get_conan_manifest_url(name, version, username, channel, auth_user):
            """
            Get a dict with all files and the download url
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            reference = ConanFileReference(name, version, username, channel)
            urls = conan_service.get_conanfile_download_urls(reference, [CONAN_MANIFEST])
            if not urls:
                raise NotFoundException("No digest found")
            return urls

        @app.route(r.v1_package_digest, method=["GET"])
        def get_package_manifest_url(name, version, username, channel, package_id, auth_user):
            """
            Get a dict with all files and the download url
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            reference = ConanFileReference(name, version, username, channel)
            package_reference = PackageReference(reference, package_id)

            urls = conan_service.get_package_download_urls(package_reference, [CONAN_MANIFEST])
            if not urls:
                raise NotFoundException("No digest found")
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            return urls_norm

        @app.route(r.recipe, method=["GET"])
        def get_recipe_snapshot(name, version, username, channel, auth_user):
            """
            Get a dictionary with all files and their each md5s
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            reference = ConanFileReference(name, version, username, channel)
            snapshot = conan_service.get_recipe_snapshot(reference)
            snapshot_norm = {filename.replace("\\", "/"): the_md5
                             for filename, the_md5 in snapshot.items()}
            return snapshot_norm

        @app.route(r.package, method=["GET"])
        def get_package_snapshot(name, version, username, channel, package_id, auth_user):
            """
            Get a dictionary with all files and their each md5s
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            reference = ConanFileReference(name, version, username, channel)
            package_reference = PackageReference(reference, package_id)
            snapshot = conan_service.get_package_snapshot(package_reference)
            snapshot_norm = {filename.replace("\\", "/"): the_md5
                             for filename, the_md5 in snapshot.items()}
            return snapshot_norm

        @app.route(r.v1_recipe_download_urls, method=["GET"])
        def get_conanfile_download_urls(name, version, username, channel, auth_user):
            """
            Get a dict with all files and the download url
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            reference = ConanFileReference(name, version, username, channel)
            urls = conan_service.get_conanfile_download_urls(reference)
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            return urls_norm

        @app.route(r.v1_package_download_urls, method=["GET"])
        def get_package_download_urls(name, version, username, channel, package_id,
                                      auth_user):
            """
            Get a dict with all packages files and the download url for each one
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            reference = ConanFileReference(name, version, username, channel)
            package_reference = PackageReference(reference, package_id)
            urls = conan_service.get_package_download_urls(package_reference)
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            return urls_norm

        @app.route(r.v1_recipe_upload_urls, method=["POST"])
        def get_conanfile_upload_urls(name, version, username, channel, auth_user):
            """
            Get a dict with all files and the upload url
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            reference = ConanFileReference(name, version, username, channel, DEFAULT_REVISION_V1)
            reader = codecs.getreader("utf-8")
            filesizes = json.load(reader(request.body))
            urls = conan_service.get_conanfile_upload_urls(reference, filesizes)
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            app.server_store.update_last_revision(reference)
            return urls_norm

        @app.route(r.v1_package_upload_urls, method=["POST"])
        def get_package_upload_urls(name, version, username, channel, package_id, auth_user):
            """
            Get a dict with all files and the upload url
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            reference = ConanFileReference(name, version, username, channel, DEFAULT_REVISION_V1)
            package_reference = PackageReference(reference, package_id, DEFAULT_REVISION_V1)

            reader = codecs.getreader("utf-8")
            filesizes = json.load(reader(request.body))
            urls = conan_service.get_package_upload_urls(package_reference, filesizes)
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            app.server_store.update_last_package_revision(package_reference)
            return urls_norm
