import codecs
import json

from bottle import request

from conans import DEFAULT_REVISION_V1
from conans.errors import NotFoundException, RecipeNotFoundException, PackageNotFoundException
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONAN_MANIFEST
from conans.server.rest.bottle_routes import BottleRoutes
from conans.server.service.v1.service import ConanService


class ConanController(object):
    """
        Serve requests related with Conan
    """
    @staticmethod
    def attach_to(app):

        r = BottleRoutes()

        @app.route(r.v1_recipe_digest, method=["GET"])
        def get_recipe_manifest_url(name, version, username, channel, auth_user):
            """
            Get a dict with all files and the download url
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            ref = ConanFileReference(name, version, username, channel)
            urls = conan_service.get_conanfile_download_urls(ref, [CONAN_MANIFEST])
            if not urls:
                raise RecipeNotFoundException(ref)
            return urls

        @app.route(r.v1_package_digest, method=["GET"])
        def get_package_manifest_url(name, version, username, channel, package_id, auth_user):
            """
            Get a dict with all files and the download url
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            ref = ConanFileReference(name, version, username, channel)
            pref = PackageReference(ref, package_id)

            urls = conan_service.get_package_download_urls(pref, [CONAN_MANIFEST])
            if not urls:
                raise PackageNotFoundException(pref)
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            return urls_norm

        @app.route(r.recipe, method=["GET"])
        def get_recipe_snapshot(name, version, username, channel, auth_user):
            """
            Get a dictionary with all files and their each md5s
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            ref = ConanFileReference(name, version, username, channel)
            snapshot = conan_service.get_recipe_snapshot(ref)
            snapshot_norm = {filename.replace("\\", "/"): the_md5
                             for filename, the_md5 in snapshot.items()}
            return snapshot_norm

        @app.route(r.package, method=["GET"])
        def get_package_snapshot(name, version, username, channel, package_id, auth_user):
            """
            Get a dictionary with all files and their each md5s
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            ref = ConanFileReference(name, version, username, channel)
            pref = PackageReference(ref, package_id)
            snapshot = conan_service.get_package_snapshot(pref)
            snapshot_norm = {filename.replace("\\", "/"): the_md5
                             for filename, the_md5 in snapshot.items()}
            return snapshot_norm

        @app.route(r.v1_recipe_download_urls, method=["GET"])
        def get_conanfile_download_urls(name, version, username, channel, auth_user):
            """
            Get a dict with all files and the download url
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            ref = ConanFileReference(name, version, username, channel)
            try:
                urls = conan_service.get_conanfile_download_urls(ref)
            except NotFoundException:
                raise RecipeNotFoundException(ref)
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            return urls_norm

        @app.route(r.v1_package_download_urls, method=["GET"])
        def get_package_download_urls(name, version, username, channel, package_id,
                                      auth_user):
            """
            Get a dict with all packages files and the download url for each one
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            ref = ConanFileReference(name, version, username, channel)
            pref = PackageReference(ref, package_id)
            try:
                urls = conan_service.get_package_download_urls(pref)
            except NotFoundException:
                raise PackageNotFoundException(pref)

            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            return urls_norm

        @app.route(r.v1_recipe_upload_urls, method=["POST"])
        def get_conanfile_upload_urls(name, version, username, channel, auth_user):
            """
            Get a dict with all files and the upload url
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            ref = ConanFileReference(name, version, username, channel, DEFAULT_REVISION_V1)
            reader = codecs.getreader("utf-8")
            filesizes = json.load(reader(request.body))
            urls = conan_service.get_conanfile_upload_urls(ref, filesizes)
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            app.server_store.update_last_revision(ref)
            return urls_norm

        @app.route(r.v1_package_upload_urls, method=["POST"])
        def get_package_upload_urls(name, version, username, channel, package_id, auth_user):
            """
            Get a dict with all files and the upload url
            """
            conan_service = ConanService(app.authorizer, app.server_store, auth_user)
            ref = ConanFileReference(name, version, username, channel, DEFAULT_REVISION_V1)
            pref = PackageReference(ref, package_id, DEFAULT_REVISION_V1)

            reader = codecs.getreader("utf-8")
            filesizes = json.load(reader(request.body))
            urls = conan_service.get_package_upload_urls(pref, filesizes)
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            app.server_store.update_last_package_revision(pref)
            return urls_norm
