from conans.server.rest.controllers.conan_controller import ConanController
from conans.model.ref import ConanFileReference, PackageReference
from conans.server.service.service import ConanService


class ConanControllerV2(ConanController):
    """
        Serve requests related with Conan
    """
    def attach_to(self, app):
        conan_route = super(ConanControllerV2, self).attach_to(app)

        @app.route("%s/download_urls" % conan_route, method=["GET"])
        def get_conanfile_download_urls(conanname, version, username, channel, auth_user):
            """
            Get a dict with all files and the download url
            """
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reference = ConanFileReference(conanname, version, username, channel)
            reference, urls = conan_service.get_conanfile_download_urls(reference)
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            return {"reference": str(reference), "files": urls_norm}

        @app.route('%s/packages/:package_id/download_urls' % conan_route, method=["GET"])
        def get_package_download_urls(conanname, version, username, channel, package_id,
                                      auth_user):
            """
            Get a dict with all packages files and the download url for each one
            """
            conan_service = ConanService(app.authorizer, app.file_manager, auth_user)
            reference = ConanFileReference(conanname, version, username, channel)
            package_reference = PackageReference(reference, package_id)
            package_reference, urls = conan_service.get_package_download_urls(package_reference)
            urls_norm = {filename.replace("\\", "/"): url for filename, url in urls.items()}
            return {"reference": str(package_reference), "files": urls_norm}

