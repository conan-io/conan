from conans.server.rest.controllers.controller import Controller
from bottle import request
from conans.model.ref import ConanFileReference, PackageReference
from conans.server.service.service import ConanService, SearchService
from conans.errors import NotFoundException
import json
from conans.paths import CONAN_MANIFEST
import os
import codecs


class ConanController(Controller):
    """
        Serve requests related with Conan
    """
    def attach_to(self, app):

        conan_route = '%s/:conanname/:version/:username/:channel' % self.route

        @app.route("/ping", method=["GET"])
        def ping():
            """
            Response OK. Useful to get server capabilities (version_checker bottle plugin)
            """
            return

        @app.route("%s/digest" % conan_route, method=["GET"])
        def get_conan_digest_url(conanname, version, username, channel, auth_user):
            """
            Get a dict with all files and the download url
            """
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reference = ConanFileReference(conanname, version, username, channel)
            urls = conan_service.get_conanfile_download_urls(reference, [CONAN_MANIFEST])
            if not urls:
                raise NotFoundException("No digest found")
            return urls

        @app.route("%s/packages/:package_id/digest" % conan_route, method=["GET"])
        def get_package_digest_url(conanname, version, username, channel, package_id, auth_user):
            """
            Get a dict with all files and the download url
            """
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reference = ConanFileReference(conanname, version, username, channel)
            package_reference = PackageReference(reference, package_id)

            urls = conan_service.get_package_download_urls(package_reference, [CONAN_MANIFEST])
            if not urls:
                raise NotFoundException("No digest found")
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            return urls_norm

        @app.route(conan_route, method=["GET"])
        def get_conanfile_snapshot(conanname, version, username, channel, auth_user):
            """
            Get a dictionary with all files and their each md5s
            """
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reference = ConanFileReference(conanname, version, username, channel)
            snapshot = conan_service.get_conanfile_snapshot(reference)
            snapshot_norm = {filename.replace("\\", "/"): the_md5
                             for filename, the_md5 in snapshot.items()}
            return snapshot_norm

        @app.route('%s/packages/:package_id' % conan_route, method=["GET"])
        def get_package_snapshot(conanname, version, username, channel, package_id, auth_user):
            """
            Get a dictionary with all files and their each md5s
            """
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reference = ConanFileReference(conanname, version, username, channel)
            package_reference = PackageReference(reference, package_id)
            snapshot = conan_service.get_package_snapshot(package_reference)
            snapshot_norm = {filename.replace("\\", "/"): the_md5
                             for filename, the_md5 in snapshot.items()}
            return snapshot_norm

        @app.route("%s/download_urls" % conan_route, method=["GET"])
        def get_conanfile_download_urls(conanname, version, username, channel, auth_user):
            """
            Get a dict with all files and the download url
            """
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reference = ConanFileReference(conanname, version, username, channel)
            urls = conan_service.get_conanfile_download_urls(reference)
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            return urls_norm

        @app.route('%s/packages/:package_id/download_urls' % conan_route, method=["GET"])
        def get_package_download_urls(conanname, version, username, channel, package_id,
                                      auth_user):
            """
            Get a dict with all packages files and the download url for each one
            """
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reference = ConanFileReference(conanname, version, username, channel)
            package_reference = PackageReference(reference, package_id)
            urls = conan_service.get_package_download_urls(package_reference)
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            return urls_norm

        @app.route("%s/upload_urls" % conan_route, method=["POST"])
        def get_conanfile_upload_urls(conanname, version, username, channel, auth_user):
            """
            Get a dict with all files and the upload url
            """
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reference = ConanFileReference(conanname, version, username, channel)
            reader = codecs.getreader("utf-8")
            filesizes = json.load(reader(request.body))
            urls = conan_service.get_conanfile_upload_urls(reference, filesizes)
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            return urls_norm

        @app.route('%s/packages/:package_id/upload_urls' % conan_route, method=["POST"])
        def get_package_upload_urls(conanname, version, username, channel, package_id, auth_user):
            """
            Get a dict with all files and the upload url
            """
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reference = ConanFileReference(conanname, version, username, channel)
            package_reference = PackageReference(reference, package_id)
            reader = codecs.getreader("utf-8")
            filesizes = json.load(reader(request.body))
            urls = conan_service.get_package_upload_urls(package_reference, filesizes)
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            return urls_norm

        @app.route('%s/search' % self.route, method=["GET"])
        def search(auth_user):
            pattern = request.params.get("q", None)
            ignorecase = request.params.get("ignorecase", True)
            if isinstance(ignorecase, str):
                ignorecase = False if 'false' == ignorecase.lower() else True
            search_service = SearchService(app.authorizer, app.search_manager, auth_user)
            references = [str(ref) for ref in search_service.search(pattern, ignorecase)]
            return {"results": references}

        @app.route('%s/search' % conan_route, method=["GET"])
        def search_packages(conanname, version, username, channel, auth_user):
            query = request.params.get("q", None)
            search_service = SearchService(app.authorizer, app.search_manager, auth_user)
            conan_reference = ConanFileReference(conanname, version, username, channel)
            info = search_service.search_packages(conan_reference, query)
            return info

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
