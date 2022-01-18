from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.client.cmd.uploader import UploadChecker, PackagePreparator, UploadExecutor


class UploadAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def check_integrity(self, upload_data):
        app = ConanApp(self.conan_api.cache_folder)
        checker = UploadChecker(app)
        checker.check(upload_data)

    @api_method
    def simulate(self, upload_data, remote, force=False):
        """Compress the recipes and packages and fill the upload_data objects
        with the complete information. It doesn't perform the upload"""
        app = ConanApp(self.conan_api.cache_folder)
        app.load_remotes([remote])
        preparator = PackagePreparator(app)
        preparator.prepare(upload_data, remote, force)

    @api_method
    def bundle(self, upload_bundle, remote, retry, retry_wait, force=False):
        app = ConanApp(self.conan_api.cache_folder)
        app.load_remotes([remote])
        preparator = PackagePreparator(app)
        preparator.prepare(upload_bundle, remote, force)

        app.remote_manager.check_credentials(remote)
        executor = UploadExecutor(app)
        executor.upload(upload_bundle, retry, retry_wait, remote, force)

