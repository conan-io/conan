import os

from conan.api.output import ConanOutput
from conan.internal.conan_app import ConanApp
from conans.client.cmd.uploader import PackagePreparator, UploadExecutor, UploadUpstreamChecker
from conans.client.downloaders.download_cache import DownloadCache
from conans.client.pkg_sign import PkgSignaturesPlugin
from conans.client.rest.file_uploader import FileUploader
from conans.errors import ConanException


class UploadAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def check_upstream(self, package_list, remote, force=False):
        """Check if the artifacts are already in the specified remote, skipping them from
        the package_list in that case"""
        app = ConanApp(self.conan_api.cache_folder)
        for ref, bundle in package_list.refs():
            layout = app.cache.ref_layout(ref)
            conanfile_path = layout.conanfile()
            conanfile = app.loader.load_basic(conanfile_path)
            if conanfile.upload_policy == "skip":
                ConanOutput().info(f"{ref}: Skipping upload of binaries, "
                                   "because upload_policy='skip'")
                bundle["packages"] = {}

        UploadUpstreamChecker(app).check(package_list, remote, force)

    def prepare(self, package_list, enabled_remotes):
        """Compress the recipes and packages and fill the upload_data objects
        with the complete information. It doesn't perform the upload nor checks upstream to see
        if the recipe is still there"""
        app = ConanApp(self.conan_api.cache_folder)
        preparator = PackagePreparator(app)
        preparator.prepare(package_list, enabled_remotes)
        signer = PkgSignaturesPlugin(app.cache)
        # This might add files entries to package_list with signatures
        signer.sign(package_list)

    def upload(self, package_list, remote):
        app = ConanApp(self.conan_api.cache_folder)
        app.remote_manager.check_credentials(remote)
        executor = UploadExecutor(app)
        executor.upload(package_list, remote)

    def upload_backup_sources(self, package_list):
        app = ConanApp(self.conan_api.cache_folder)
        config = app.cache.new_config
        # TODO: Rethink this conf, does this live in core?
        url = config.get("tools.backup_sources:url")
        if url is None:
            return
        url = url if url.endswith("/") else url + "/"
        download_cache_path = config.get("tools.files.download:download_cache")
        if download_cache_path is None:
            raise ConanException("Need to define 'tools.files.download:download_cache'")

        files = DownloadCache(download_cache_path).get_files_to_upload(package_list)
        uploader = FileUploader(app.requester, verify=False, config=config)
        # TODO: Dedup and list files
        for file in files:
            # TODO: Skip uploading files that are already present in the remote.
            # Check Artifactory's HEAD
            basename = os.path.basename(file)
            full_url = url + basename
            exist = uploader.exist(full_url, auth=None)
            if not exist:
                ConanOutput().info(f"Uploading file '{basename} to server")
                uploader.upload(full_url, file, dedup=False, auth=None)
            else:
                ConanOutput().info(f"File '{basename} already in server, skipping upload")
        return files
